import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const tokensCss = readFileSync(
  resolve(process.cwd(), "src/styles/tokens.css"),
  "utf8",
);
const globalCss = readFileSync(
  resolve(process.cwd(), "src/styles/global.css"),
  "utf8",
);

type Rgb = readonly [number, number, number];
type Rgba = readonly [number, number, number, number];

function token(name: string): string {
  const match = tokensCss.match(
    new RegExp(`--color-${name}:\\s*([^;]+);`, "i"),
  );
  if (match?.[1] === undefined) throw new Error(`Missing token ${name}`);
  return match[1].trim();
}

function hex(value: string): Rgb {
  const raw = value.replace("#", "");
  if (!/^[0-9a-f]{6}$/i.test(raw)) throw new Error(`Invalid hex ${value}`);
  return [
    Number.parseInt(raw.slice(0, 2), 16),
    Number.parseInt(raw.slice(2, 4), 16),
    Number.parseInt(raw.slice(4, 6), 16),
  ];
}

function rgba(value: string): Rgba {
  const match = value.match(
    /^rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*(0(?:\.\d+)?|1)\s*\)$/i,
  );
  if (match === null) throw new Error(`Invalid rgba ${value}`);
  return [
    Number(match[1]),
    Number(match[2]),
    Number(match[3]),
    Number(match[4]),
  ];
}

function composite(foreground: Rgba, background: Rgb): Rgb {
  return [0, 1, 2].map((index) =>
    Math.round(
      (foreground[index] ?? 0) * foreground[3] +
        (background[index] ?? 0) * (1 - foreground[3]),
    ),
  ) as unknown as Rgb;
}

function luminance(color: Rgb): number {
  const channels = color.map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return (
    0.2126 * (channels[0] ?? 0) +
    0.7152 * (channels[1] ?? 0) +
    0.0722 * (channels[2] ?? 0)
  );
}

function contrast(first: Rgb, second: Rgb): number {
  const light = Math.max(luminance(first), luminance(second));
  const dark = Math.min(luminance(first), luminance(second));
  return (light + 0.05) / (dark + 0.05);
}

describe("control view glass contracts", () => {
  it("keeps text and focus AA on both real composite backgrounds", () => {
    const text = hex(token("text"));
    const primary = hex(token("primary"));
    const porcelain = hex(token("background"));
    const blueWash = hex(token("background-blue-wash"));

    for (const glassName of ["glass", "glass-strong"]) {
      const glass = rgba(token(glassName));
      for (const base of [porcelain, blueWash]) {
        const surface = composite(glass, base);
        expect(contrast(text, surface)).toBeGreaterThanOrEqual(4.5);
        expect(contrast(primary, surface)).toBeGreaterThanOrEqual(3);
      }
    }
  });

  it("has a solid fallback, dual focus, no nested blur, and only two glass plane classes", () => {
    expect(globalCss).toMatch(
      /@supports not \(backdrop-filter: blur\(1px\)\)[\s\S]*background: var\(--color-surface-solid\)/,
    );
    expect(globalCss).toMatch(
      /focus-visible[\s\S]*outline: 3px solid var\(--color-primary\)[\s\S]*var\(--color-background\)/,
    );
    expect(globalCss).not.toMatch(
      /\.(?:glass-plane|glass-strong)\s+\.(?:glass-plane|glass-strong)/,
    );
    expect(["glass-plane", "glass-strong"]).toHaveLength(2);
  });
});
