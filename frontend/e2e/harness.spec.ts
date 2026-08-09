import { existsSync } from "node:fs";
import { basename, dirname } from "node:path";

import { expect, test } from "./support/fixtures";
import { runtimeFile } from "./support/global-setup";

test("uses isolated loopback HTTPS state without a global TLS bypass", async ({
  page,
  runtime,
}) => {
  expect(runtime.baseURL).toMatch(/^https:\/\/127\.0\.0\.1:\d+$/);
  expect(existsSync(runtime.root)).toBe(true);
  expect(existsSync(runtime.ca)).toBe(true);
  expect(existsSync(runtime.cert)).toBe(true);
  expect(existsSync(runtime.key)).toBe(true);
  expect(basename(runtimeFile)).toBe("runtime.json");
  expect(basename(dirname(runtimeFile))).toMatch(
    /^personal-finance-e2e-control-/,
  );
  await page.goto(runtime.baseURL);
  await expect(
    page.getByRole("heading", { name: "Acceder", exact: true }),
  ).toBeVisible();
});
