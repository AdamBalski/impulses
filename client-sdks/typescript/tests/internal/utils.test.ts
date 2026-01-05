import { describe, expect, it } from "vitest";

import { parseDuration } from "../../src/internal/utils.js";

describe("parseDuration", () => {
  it("parses positive durations", () => {
    const result = parseDuration("1d2h30m45s500ms");
    expect(result).toBe(
      24 * 60 * 60 * 1000 +
        2 * 60 * 60 * 1000 +
        30 * 60 * 1000 +
        45 * 1000 +
        500
    );
  });

  it("parses negative durations", () => {
    const result = parseDuration("-1d-2h-30m-45s-500ms");
    expect(result).toBe(
      -(24 * 60 * 60 * 1000) -
        2 * 60 * 60 * 1000 -
        30 * 60 * 1000 -
        45 * 1000 -
        500
    );
  });

  it("allows mixing positive and negative parts", () => {
    const result = parseDuration("2h-30m15s");
    expect(result).toBe(2 * 60 * 60 * 1000 - 30 * 60 * 1000 + 15 * 1000);
  });

  it("throws for zero duration string", () => {
    expect(parseDuration("0d0h0m")).toBe(0);
  });
});
