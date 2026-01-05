import { describe, it, expect } from "vitest";
import { Datapoint, DatapointSeries } from "../../src/models";
import { compute } from "../../src/dsl/interpreter";
import type { ImpulsesClient } from "../../src/client";

function stubClient(streams: Record<string, DatapointSeries>): ImpulsesClient {
  return {
    fetchDatapoints: async (metricName: string) => {
      const stream = streams[metricName];
      if (!stream) {
        throw new Error(`Unknown metric '${metricName}'`);
      }
      return stream;
    },
  } as unknown as ImpulsesClient;
}

describe("DSL interpreter", () => {
  it("evaluates programs and exposes stream bindings", async () => {
    const deltas = new DatapointSeries([
      new Datapoint(0, -5),
      new Datapoint(15 * 60 * 1000, 6),
      new Datapoint(30 * 60 * 1000, 3),
      new Datapoint(90 * 60 * 1000, 10),
    ]);

    const client = stubClient({ deltas });

    const program = `
      (define deltas (data "deltas"))
      (define expenses (filter deltas (> 0)))
      (define expenses-prefix (prefix expenses sum))
      (define expenses-window (window expenses "1h" sum))
      (define threshold 10)
    `;

    const result = await compute(client, program);

    expect(result.has("threshold")).toBe(false);
    expect(result.get("deltas")?.toDTO()).toEqual(deltas.toDTO());
    expect(result.get("expenses")?.toDTO()).toEqual([
      { timestamp: 15 * 60 * 1000, value: 6, dimensions: {} },
      { timestamp: 30 * 60 * 1000, value: 3, dimensions: {} },
      { timestamp: 90 * 60 * 1000, value: 10, dimensions: {} },
    ]);
    expect(result.get("expenses-prefix")?.toDTO()).toEqual([
      { timestamp: 15 * 60 * 1000, value: 6, dimensions: {} },
      { timestamp: 30 * 60 * 1000, value: 9, dimensions: {} },
      { timestamp: 90 * 60 * 1000, value: 19, dimensions: {} },
    ]);
    expect(result.get("expenses-window")?.toDTO()).toEqual([
      { timestamp: 15 * 60 * 1000, value: 6, dimensions: {} },
      { timestamp: 30 * 60 * 1000, value: 9, dimensions: {} },
      { timestamp: 75 * 60 * 1000, value: 3, dimensions: {} },
      { timestamp: 90 * 60 * 1000, value: 10, dimensions: {} },
    ]);
  });

  it("supports map, filter (value and dimension predicates), logical combinators, and compose", async () => {
    const transactions = new DatapointSeries(
      [
        new Datapoint(0, -5, { category: "dining", method: "card" }),
        new Datapoint(60_000, -7, { category: "groceries", method: "cash" }),
        new Datapoint(120_000, 10, { category: "income", method: "transfer" }),
        new Datapoint(180_000, -3, { category: "dining", method: "virtual" }),
        new Datapoint(240_000, -2, { category: "fees" }),
      ],
      0
    );
    const balance = new DatapointSeries(
      [
        new Datapoint(1_000, 120),
        new Datapoint(2_000, 80),
      ],
      100
    );
    const avgExpense = new DatapointSeries(
      [
        new Datapoint(1_500, 15),
        new Datapoint(3_000, 20),
      ],
      10
    );

    const client = stubClient({
      transactions,
      balance,
      "avg-expense": avgExpense,
    });

    const program = `
      (define transactions (data "transactions"))
      (define balance-stream (data "balance"))
      (define avg-expense (data "avg-expense"))

      (define expenses (filter transactions (< 0)))
      (define income (filter transactions (not (< 0))))

      (define dining-expenses
        (filter transactions
          (and (< 0) (dimension-is "category" "dining"))))
      (define card-or-virtual-expenses
        (filter transactions
          (and (< 0)
               (or (dimension-is "method" "card")
                   (dimension-is "method" "virtual")))))
      (define missing-method-expenses
        (filter transactions
          (and (< 0) (no-dimension "method"))))
      (define expense-magnitudes
        (map expenses
             (lambda (value) (* -1 value))))
      (define expense-buffers
        (map expenses
             (lambda (value) (* -1 value))
             (lambda (value) (+ value 1))))
      (define runway
        (compose balance-stream avg-expense
                 (lambda (balance avg)
                   (/ balance avg))))
    `;

    const result = await compute(client, program);

    expect(result.get("income")?.toDTO()).toEqual([
        { timestamp: 120_000, value: 10, dimensions: { category: "income", method: "transfer" } }
    ]);
    expect(result.get("expenses")?.toDTO()).toEqual([
      { timestamp: 0, value: -5, dimensions: { category: "dining", method: "card" } },
      { timestamp: 60_000, value: -7, dimensions: { category: "groceries", method: "cash" } },
      { timestamp: 180_000, value: -3, dimensions: { category: "dining", method: "virtual" } },
      { timestamp: 240_000, value: -2, dimensions: { category: "fees" } },
    ]);
    expect(result.get("dining-expenses")?.toDTO()).toEqual([
      { timestamp: 0, value: -5, dimensions: { category: "dining", method: "card" } },
      { timestamp: 180_000, value: -3, dimensions: { category: "dining", method: "virtual" } },
    ]);
    expect(result.get("card-or-virtual-expenses")?.toDTO()).toEqual([
      { timestamp: 0, value: -5, dimensions: { category: "dining", method: "card" } },
      { timestamp: 180_000, value: -3, dimensions: { category: "dining", method: "virtual" } },
    ]);
    expect(result.get("missing-method-expenses")?.toDTO()).toEqual([
      { timestamp: 240_000, value: -2, dimensions: { category: "fees" } },
    ]);
    expect(result.get("expense-magnitudes")?.toDTO()).toEqual([
      { timestamp: 0, value: 5, dimensions: { category: "dining", method: "card" } },
      { timestamp: 60_000, value: 7, dimensions: { category: "groceries", method: "cash" } },
      { timestamp: 180_000, value: 3, dimensions: { category: "dining", method: "virtual" } },
      { timestamp: 240_000, value: 2, dimensions: { category: "fees" } },
    ]);
    expect(result.get("expense-buffers")?.toDTO()).toEqual([
      { timestamp: 0, value: 6, dimensions: { category: "dining", method: "card" } },
      { timestamp: 60_000, value: 8, dimensions: { category: "groceries", method: "cash" } },
      { timestamp: 180_000, value: 4, dimensions: { category: "dining", method: "virtual" } },
      { timestamp: 240_000, value: 3, dimensions: { category: "fees" } },
    ]);
    expect(result.get("runway")?.toDTO()).toEqual([
      { timestamp: 1_000, value: 12, dimensions: {} },
      { timestamp: 1_500, value: 8, dimensions: {} },
      { timestamp: 2_000, value: 5.333333333333333, dimensions: {} },
      { timestamp: 3_000, value: 4, dimensions: {} },
    ]);
  });
});
