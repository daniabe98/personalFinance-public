import { describe, expect, it } from "vitest";

import { evaluateAuditReport, validateAuditReport } from "./npm-audit-gate.mjs";

const NOW = new Date("2026-08-03T20:30:00Z");
const FINDING_ID = "GHSA-QWWW-VCR4-C8H2";

function auditReport(...advisories) {
  return {
    auditReportVersion: 2,
    vulnerabilities: {
      "react-router": {
        severity: "high",
        via: advisories,
      },
      "react-router-dom": {
        severity: "high",
        via: ["react-router"],
      },
    },
  };
}

function advisory(findingId = FINDING_ID, severity = "high") {
  return {
    source: 1124282,
    severity,
    url: `https://github.com/advisories/${findingId}`,
  };
}

function decisionStore(expiresAt = "2026-09-02T20:21:35Z") {
  return {
    decisions: [
      {
        id: "DEC-2026-08-03-BF075BEF",
        riskCategory: "risk-acceptance",
        findingId: "GHSA-qwww-vcr4-c8h2",
        severity: "high",
        status: "active",
        expiresAt,
      },
    ],
  };
}

describe("npm audit risk gate", () => {
  it("accepts a transitive advisory covered by a current ai-eng decision", () => {
    const result = evaluateAuditReport(
      auditReport(advisory()),
      decisionStore(),
      NOW,
    );

    expect(result.rejectedFindings).toEqual([]);
    expect(result.unresolvedPackages).toEqual([]);
    expect(result.acceptedFindings).toEqual([
      expect.objectContaining({
        findingId: FINDING_ID,
        decisionId: "DEC-2026-08-03-BF075BEF",
        packages: ["react-router", "react-router-dom"],
      }),
    ]);
  });

  it("blocks the same advisory after its decision expires", () => {
    const result = evaluateAuditReport(
      auditReport(advisory()),
      decisionStore("2026-08-03T20:29:59Z"),
      NOW,
    );

    expect(result.acceptedFindings).toEqual([]);
    expect(result.rejectedFindings).toEqual([
      expect.objectContaining({ findingId: FINDING_ID }),
    ]);
  });

  it("blocks a new advisory that has no matching decision", () => {
    const result = evaluateAuditReport(
      auditReport(advisory(), advisory("GHSA-aaaa-bbbb-cccc")),
      decisionStore(),
      NOW,
    );

    expect(result.rejectedFindings).toEqual([
      expect.objectContaining({ findingId: "GHSA-AAAA-BBBB-CCCC" }),
    ]);
  });

  it("blocks an advisory that escalates above the accepted severity", () => {
    const result = evaluateAuditReport(
      auditReport(advisory(FINDING_ID, "critical")),
      decisionStore(),
      NOW,
    );

    expect(result.acceptedFindings).toEqual([]);
    expect(result.rejectedFindings).toEqual([
      expect.objectContaining({ findingId: FINDING_ID, severity: "critical" }),
    ]);
  });

  it("fails closed when a blocking package cannot be mapped to an advisory", () => {
    const result = evaluateAuditReport(
      {
        vulnerabilities: {
          opaque: { severity: "critical", via: [] },
        },
      },
      decisionStore(),
      NOW,
    );

    expect(result.unresolvedPackages).toEqual(["opaque"]);
  });

  it("rejects malformed npm output instead of treating it as a clean audit", () => {
    expect(() => validateAuditReport({})).toThrow(/npm audit report version 2/);
  });
});
