import { readFileSync } from "node:fs";
import {
  chromium,
  test as base,
  expect,
  type Browser,
  type Page,
} from "@playwright/test";

import { runtimeFile } from "./global-setup";

interface Runtime {
  readonly root: string;
  readonly workspace: string;
  readonly ca: string;
  readonly cert: string;
  readonly key: string;
  readonly spki: string;
  readonly username: string;
  readonly password: string;
  readonly server_python: string;
  readonly installed_site: string;
  readonly baseURL: string;
}

export const test = base.extend<{ runtime: Runtime }, { browser: Browser }>({
  browser: [
    async ({ browserName: _browserName }, use) => {
      const runtime = JSON.parse(readFileSync(runtimeFile, "utf8")) as Runtime;
      const browser = await chromium.launch({
        args: [`--ignore-certificate-errors-spki-list=${runtime.spki}`],
      });
      await use(browser);
      await browser.close();
    },
    { scope: "worker" },
  ],
  runtime: async ({ browserName: _browserName }, use) => {
    await use(JSON.parse(readFileSync(runtimeFile, "utf8")) as Runtime);
  },
});

export async function login(page: Page, runtime: Runtime): Promise<void> {
  await page.goto(runtime.baseURL);
  await page.getByLabel("Usuario").fill(runtime.username);
  await page.getByLabel("Contraseña").fill(runtime.password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(
    page.getByRole("navigation", { name: "Navegación principal" }),
  ).toBeVisible();
}

export { expect };
