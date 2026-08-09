import { describe, expect, it } from "vitest";

import { localCalendarDate } from "./local-date";

describe("localCalendarDate", () => {
  it("uses the household calendar day rather than the UTC day", () => {
    const afterMidnightInMadrid = new Date("2026-07-30T22:30:00.000Z");
    afterMidnightInMadrid.getTimezoneOffset = () => -120;

    expect(localCalendarDate(afterMidnightInMadrid)).toBe("2026-07-31");
  });
});
