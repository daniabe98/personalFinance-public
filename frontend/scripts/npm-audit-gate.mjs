import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const BLOCKING_SEVERITIES = new Set(["moderate", "high", "critical"]);
const SEVERITY_RANK = new Map([
  ["moderate", 1],
  ["high", 2],
  ["critical", 3],
]);
const GHSA_PATTERN = /GHSA-[0-9a-z-]+/i;

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function advisoryId(advisory) {
  const url = typeof advisory.url === "string" ? advisory.url : "";
  const ghsa = url.match(GHSA_PATTERN)?.[0];
  if (ghsa !== undefined) {
    return ghsa.toUpperCase();
  }
  if (
    typeof advisory.source === "number" ||
    typeof advisory.source === "string"
  ) {
    return `npm:${advisory.source}`;
  }
  return undefined;
}

function resolveAdvisories(packageName, vulnerabilities, visited = new Set()) {
  if (visited.has(packageName)) {
    return [];
  }
  const vulnerability = vulnerabilities[packageName];
  if (!isRecord(vulnerability) || !Array.isArray(vulnerability.via)) {
    return [];
  }

  const nextVisited = new Set(visited).add(packageName);
  return vulnerability.via.flatMap((via) => {
    if (typeof via === "string") {
      return resolveAdvisories(via, vulnerabilities, nextVisited);
    }
    return isRecord(via) ? [via] : [];
  });
}

function decisionEntries(decisionStore) {
  if (!isRecord(decisionStore)) {
    return [];
  }
  const entries = [decisionStore.acceptances, decisionStore.decisions]
    .filter(Array.isArray)
    .flat()
    .filter(isRecord);
  const unique = new Map();
  for (const entry of entries) {
    const key = typeof entry.id === "string" ? entry.id : JSON.stringify(entry);
    unique.set(key, entry);
  }
  return [...unique.values()];
}

function activeAcceptance(findingId, findingSeverity, decisionStore, now) {
  return decisionEntries(decisionStore).find((entry) => {
    if (
      entry.riskCategory !== "risk-acceptance" ||
      entry.status !== "active" ||
      typeof entry.findingId !== "string" ||
      entry.findingId.toUpperCase() !== findingId.toUpperCase() ||
      typeof entry.severity !== "string" ||
      (SEVERITY_RANK.get(entry.severity) ?? 0) <
        (SEVERITY_RANK.get(findingSeverity) ?? Number.POSITIVE_INFINITY) ||
      typeof entry.expiresAt !== "string"
    ) {
      return false;
    }
    const expiresAt = Date.parse(entry.expiresAt);
    return Number.isFinite(expiresAt) && expiresAt > now.getTime();
  });
}

export function evaluateAuditReport(
  auditReport,
  decisionStore,
  now = new Date(),
) {
  const vulnerabilities = isRecord(auditReport?.vulnerabilities)
    ? auditReport.vulnerabilities
    : {};
  const findings = new Map();
  const unresolvedPackages = [];

  for (const [packageName, vulnerability] of Object.entries(vulnerabilities)) {
    if (
      !isRecord(vulnerability) ||
      !BLOCKING_SEVERITIES.has(vulnerability.severity)
    ) {
      continue;
    }
    const blockingAdvisories = resolveAdvisories(
      packageName,
      vulnerabilities,
    ).filter((advisory) => BLOCKING_SEVERITIES.has(advisory.severity));
    if (blockingAdvisories.length === 0) {
      unresolvedPackages.push(packageName);
      continue;
    }
    for (const advisory of blockingAdvisories) {
      const findingId = advisoryId(advisory);
      if (findingId === undefined) {
        unresolvedPackages.push(packageName);
        continue;
      }
      const existing = findings.get(findingId) ?? {
        findingId,
        packages: new Set(),
        severity: advisory.severity,
      };
      existing.packages.add(packageName);
      if (
        (SEVERITY_RANK.get(advisory.severity) ?? 0) >
        (SEVERITY_RANK.get(existing.severity) ?? 0)
      ) {
        existing.severity = advisory.severity;
      }
      findings.set(findingId, existing);
    }
  }

  const acceptedFindings = [];
  const rejectedFindings = [];
  for (const finding of findings.values()) {
    const acceptance = activeAcceptance(
      finding.findingId,
      finding.severity,
      decisionStore,
      now,
    );
    const normalized = {
      findingId: finding.findingId,
      packages: [...finding.packages].sort(),
      severity: finding.severity,
    };
    if (acceptance === undefined) {
      rejectedFindings.push(normalized);
    } else {
      acceptedFindings.push({
        ...normalized,
        decisionId: acceptance.id,
        expiresAt: acceptance.expiresAt,
      });
    }
  }

  return {
    acceptedFindings,
    rejectedFindings,
    unresolvedPackages: [...new Set(unresolvedPackages)].sort(),
  };
}

export function validateAuditReport(auditReport) {
  if (
    auditReport.auditReportVersion !== 2 ||
    !isRecord(auditReport.vulnerabilities)
  ) {
    throw new TypeError(
      "expected npm audit report version 2 with a vulnerabilities object",
    );
  }
}

function readJson(label, contents) {
  try {
    const parsed = JSON.parse(contents);
    if (!isRecord(parsed)) {
      throw new TypeError("expected a JSON object");
    }
    return parsed;
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`${label} is not valid JSON: ${detail}`);
  }
}

function main() {
  const invocation =
    process.platform === "win32"
      ? {
          command: process.env.ComSpec ?? "cmd.exe",
          args: ["/d", "/s", "/c", "npm audit --json"],
        }
      : { command: "npm", args: ["audit", "--json"] };
  const audit = spawnSync(invocation.command, invocation.args, {
    cwd: resolve(dirname(fileURLToPath(import.meta.url)), ".."),
    encoding: "utf8",
    maxBuffer: 10 * 1024 * 1024,
  });
  if (audit.error !== undefined) {
    throw audit.error;
  }
  if (audit.status !== 0 && audit.status !== 1) {
    throw new Error(
      `npm audit exited unexpectedly with status ${audit.status}`,
    );
  }
  const auditReport = readJson("npm audit output", audit.stdout);
  if (isRecord(auditReport.error)) {
    throw new Error(`npm audit failed: ${JSON.stringify(auditReport.error)}`);
  }
  validateAuditReport(auditReport);

  const repositoryRoot = resolve(
    dirname(fileURLToPath(import.meta.url)),
    "..",
    "..",
  );
  const decisionStorePath = resolve(
    repositoryRoot,
    ".ai-engineering",
    "state",
    "decision-store.json",
  );
  const decisionStore = readJson(
    "ai-eng decision store",
    readFileSync(decisionStorePath, "utf8"),
  );
  const result = evaluateAuditReport(auditReport, decisionStore);

  for (const finding of result.acceptedFindings) {
    console.log(
      `ACCEPTED ${finding.findingId} via ${finding.decisionId} until ${finding.expiresAt}`,
    );
  }
  for (const finding of result.rejectedFindings) {
    console.error(
      `BLOCKED ${finding.findingId} (${finding.severity}) in ${finding.packages.join(", ")}`,
    );
  }
  for (const packageName of result.unresolvedPackages) {
    console.error(`BLOCKED unresolved audit finding in ${packageName}`);
  }

  if (
    result.rejectedFindings.length > 0 ||
    result.unresolvedPackages.length > 0
  ) {
    process.exitCode = 1;
  } else {
    console.log(
      "Dependency audit passed: no unaccepted moderate-or-higher findings.",
    );
  }
}

const invokedPath =
  process.argv[1] === undefined
    ? undefined
    : pathToFileURL(process.argv[1]).href;
if (invokedPath === import.meta.url) {
  try {
    main();
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    console.error(`Dependency audit gate failed closed: ${detail}`);
    process.exitCode = 1;
  }
}
