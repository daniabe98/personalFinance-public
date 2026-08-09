export type MoneyParseResult =
  | { readonly ok: true; readonly value: number }
  | { readonly ok: false; readonly message: string };

const EUR_INPUT = /^-?(?:0|[1-9]\d*|[1-9]\d{0,2}(?:\.\d{3})+)(?:,\d{1,2})?$/;

export function parseEurCents(input: string): MoneyParseResult {
  const normalized = input.trim();
  if (!EUR_INPUT.test(normalized)) {
    return {
      ok: false,
      message: "Escribe un importe en euros con hasta dos decimales.",
    };
  }
  const isNegative = normalized.startsWith("-");
  const unsigned = isNegative ? normalized.slice(1) : normalized;
  const [eurosRaw = "0", centsRaw = ""] = unsigned.split(",");
  const euros = BigInt(eurosRaw.replaceAll(".", ""));
  const cents = BigInt(centsRaw.padEnd(2, "0"));
  const value = euros * 100n + cents;
  const signedValue = isNegative ? -value : value;
  if (
    signedValue > BigInt(Number.MAX_SAFE_INTEGER) ||
    signedValue < BigInt(Number.MIN_SAFE_INTEGER)
  ) {
    return { ok: false, message: "El importe es demasiado grande." };
  }
  return { ok: true, value: Number(signedValue) };
}

export function formatEurCents(cents: number): string {
  if (!Number.isSafeInteger(cents)) {
    throw new TypeError("Money must be safe integer cents");
  }
  const isNegative = cents < 0;
  const absolute = Math.abs(cents);
  const euros = Math.floor(absolute / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const fraction = (absolute % 100).toString().padStart(2, "0");
  return `${isNegative ? "-" : ""}${euros},${fraction} €`;
}
