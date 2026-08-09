import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { format } from "prettier";

const root = fileURLToPath(new URL("../", import.meta.url));
const openApiPath = new URL("../openapi.json", import.meta.url);
const outputPath = new URL("../src/api/schema.d.ts", import.meta.url);
const document = JSON.parse(readFileSync(openApiPath, "utf8"));
const schemas = document.components?.schemas;

if (typeof schemas !== "object" || schemas === null) {
  throw new Error("OpenAPI components.schemas is missing");
}

const enumNames = [
  "AccountKind",
  "CategoryKind",
  "TransactionKind",
  "TransactionStatus",
];
const interfaceNames = [
  "AccountResponse",
  "CategoryResponse",
  "CommandResponse",
  "TransactionResponse",
];

function requiredSchema(name) {
  const schema = schemas[name];
  if (typeof schema !== "object" || schema === null) {
    throw new Error(`OpenAPI schema ${name} is missing`);
  }
  return schema;
}

function typeFromSchema(schema) {
  if (typeof schema.$ref === "string") {
    return schema.$ref.split("/").at(-1);
  }
  if (Array.isArray(schema.enum)) {
    return schema.enum.map((value) => JSON.stringify(value)).join(" | ");
  }
  if (Array.isArray(schema.anyOf)) {
    return schema.anyOf.map(typeFromSchema).join(" | ");
  }
  if (schema.type === "array") {
    return `readonly ${typeFromSchema(schema.items)}[]`;
  }
  if (schema.type === "integer" || schema.type === "number") return "number";
  if (schema.type === "boolean") return "boolean";
  if (schema.type === "null") return "null";
  if (schema.type === "string") {
    return schema.default === "EUR" ? '"EUR"' : "string";
  }
  throw new Error(`Unsupported OpenAPI shape: ${JSON.stringify(schema)}`);
}

function enumDeclaration(name) {
  const schema = requiredSchema(name);
  if (!Array.isArray(schema.enum) || schema.enum.length === 0) {
    throw new Error(`OpenAPI schema ${name} is not a closed enum`);
  }
  return `export type ${name} = ${typeFromSchema(schema)};`;
}

function interfaceDeclaration(name) {
  const schema = requiredSchema(name);
  if (typeof schema.properties !== "object" || schema.properties === null) {
    throw new Error(`OpenAPI schema ${name} has no properties`);
  }
  const properties = Object.entries(schema.properties)
    .map(
      ([property, value]) =>
        `  readonly ${property}: ${typeFromSchema(value)};`,
    )
    .join("\n");
  return `export interface ${name} {\n${properties}\n}`;
}

const supplemental = `export interface SessionPrincipal {
  readonly user_id: string;
  readonly space_id: string;
  readonly username: string;
}

export interface SessionResponse extends SessionPrincipal {
  readonly csrf_token: string;
}

export interface LoginResponse {
  readonly csrf_token: string;
  readonly expires_at: string;
  readonly user_id: string;
  readonly space_id: string;
}

export interface ProblemResponse {
  readonly code: string;
  readonly detail: string;
  readonly status: number;
  readonly title: string;
}`;

const rawGenerated = [
  "/* Generated from frontend/openapi.json. Do not edit by hand. */",
  "",
  supplemental,
  "",
  ...enumNames.flatMap((name) => [enumDeclaration(name), ""]),
  ...interfaceNames.flatMap((name) => [interfaceDeclaration(name), ""]),
].join("\n");
const generated = await format(rawGenerated, { parser: "typescript" });

if (process.argv.includes("--check")) {
  const current = readFileSync(outputPath, "utf8");
  if (current !== generated) {
    process.stderr.write(
      `Generated API types are stale. Run npm run api:generate from ${root}.\n`,
    );
    process.exitCode = 1;
  }
} else {
  writeFileSync(outputPath, generated);
}
