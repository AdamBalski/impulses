import { addMonths, startOfDay, startOfYear } from "./internal/utils.js";

export type Dimensions = Record<string, string>;

export interface DatapointDTO {
  timestamp: number;
  value: number;
  dimensions?: Dimensions;
}

export class Datapoint {
  constructor(
    public readonly timestamp: number,
    public readonly value: number,
    public readonly dimensions: Dimensions = {}
  ) {}

  static fromDTO(dto: DatapointDTO): Datapoint {
    return new Datapoint(dto.timestamp, dto.value, dto.dimensions ?? {});
  }

  toDTO(): DatapointDTO {
    return {
      timestamp: this.timestamp,
      value: this.value,
      dimensions: this.dimensions,
    };
  }
}

export interface EvaluatedImpulse {
  isConstant(): boolean;
  getInitVal(): number;
  asDatapointSeries(): DatapointSeries;
}

export class ConstantImpulse implements EvaluatedImpulse {
  constructor(private readonly value: number) {}

  isConstant(): boolean {
    return true;
  }

  getInitVal(): number {
    return this.value;
  }

  asDatapointSeries(): DatapointSeries {
    throw new Error("Constant impulse cannot be converted to DatapointSeries");
  }
}

export class DatapointSeries implements Iterable<Datapoint>, EvaluatedImpulse {
  constructor(
    public readonly series: Datapoint[] = [],
    public readonly initValue = 0
  ) {}

  static fromDTO(series: DatapointDTO[], initValue = 0): DatapointSeries {
    return new DatapointSeries(series.map(Datapoint.fromDTO), initValue);
  }

  toDTO(): DatapointDTO[] {
    return this.series.map((dp) => dp.toDTO());
  }

  [Symbol.iterator](): Iterator<Datapoint> {
    return this.series[Symbol.iterator]();
  }

  get length(): number {
    return this.series.length;
  }

  isConstant(): boolean {
    return false;
  }

  getInitVal(): number {
    return this.initValue;
  }

  asDatapointSeries(): DatapointSeries {
    return this;
  }

  isEmpty(): boolean {
    return this.length === 0;
  }

  timeAt(idx: number): number {
    return this.series[idx]?.timestamp ?? 0;
  }

  valueAt(idx: number): number {
    return this.series[idx]?.value ?? this.initValue;
  }

  async filter(predicate: (dp: Datapoint) => Promise<boolean>): Promise<DatapointSeries> {
    const decisions = await Promise.all(this.series.map((dp) => predicate(dp)));
    const filtered = this.series.filter((_, idx) => decisions[idx]);
    return new DatapointSeries(filtered, this.initValue);
  }

  async map(mapper: (dp: Datapoint) => Promise<Datapoint>): Promise<DatapointSeries> {
    const mapped = await Promise.all(this.series.map((dp) => mapper(dp)));
    return new DatapointSeries(mapped, this.initValue);
  }

  shift(durationMs: number): DatapointSeries {
    const shifted = this.series.map(
      (dp) => new Datapoint(dp.timestamp + durationMs, dp.value, dp.dimensions)
    );
    return new DatapointSeries(shifted, this.initValue);
  }

  async prefixOp(operation: (values: number[]) => Promise<number>): Promise<DatapointSeries> {
    let prev = this.initValue;
    const nextSeries: Datapoint[] = [];
    for (const dp of this.series) {
      prev = await operation([prev, dp.value]);
      nextSeries.push(new Datapoint(dp.timestamp, prev, dp.dimensions));
    }
    const nextInit = await operation([this.initValue]);
    return new DatapointSeries(nextSeries, nextInit);
  }

  async slidingWindow(
    window: number,
    operation: (values: number[]) => Promise<number>,
    fluidPhaseOut = true
  ): Promise<DatapointSeries> {
    if (this.isEmpty()) {
      return new DatapointSeries([], this.initValue);
    }

    type Event = { time: number; type: "add" | "remove"; value: number };
    const events: Event[] = [];
    const insertEvent = (event: Event) => {
      const idx = events.findIndex((e) => e.time > event.time);
      if (idx === -1) {
        events.push(event);
      } else {
        events.splice(idx, 0, event);
      }
    };

    for (const dp of this.series) {
      insertEvent({ time: dp.timestamp, type: "add", value: dp.value });
    }

    const lastTimestamp = this.series[this.series.length - 1].timestamp;
    const counts = new Map<number, number>();
    let activeCount = 0;
    const bucketPromises: Promise<Datapoint>[] = [];

    while (events.length > 0) {
      const event = events.shift()!;
      if (!fluidPhaseOut && event.time > lastTimestamp) {
        break;
      }

      if (event.type === "add") {
        activeCount += 1;
        counts.set(event.value, (counts.get(event.value) ?? 0) + 1);
        insertEvent({
          time: event.time + window,
          type: "remove",
          value: event.value,
        });
      } else {
        activeCount -= 1;
        const current = counts.get(event.value) ?? 0;
        if (current <= 1) {
          counts.delete(event.value);
        } else {
          counts.set(event.value, current - 1);
        }
      }

      if (events[0]?.time === event.time) {
        continue;
      }

      if (activeCount === 0) {
        bucketPromises.push(Promise.resolve(new Datapoint(event.time, this.initValue)));
        continue;
      }

      const values: number[] = [];
      counts.forEach((count, value) => {
        for (let i = 0; i < count; i += 1) {
          values.push(value);
        }
      });
      bucketPromises.push(
        operation(values).then((aggregateValue) => new Datapoint(event.time, aggregateValue))
      );
    }

    const datapoints = await Promise.all(bucketPromises);
    if (fluidPhaseOut && datapoints.length > 0) {
      datapoints.pop();
    }

    return new DatapointSeries(datapoints, this.initValue);
  }

  async bucketize(
    duration: number,
    aggregate: (values: number[]) => Promise<number>
  ): Promise<DatapointSeries> {
    if (duration <= 0) {
      throw new Error("Bucket duration must be positive");
    }
    if (this.isEmpty()) {
      return new DatapointSeries([], this.initValue);
    }

    const firstTimestamp = this.series[0].timestamp;
    const anchor = startOfDay(firstTimestamp);
    let currentStart = anchor + Math.floor((firstTimestamp - anchor) / duration) * duration;
    const datapoints: Datapoint[] = [];
    let bucketValues: number[] = [];

    const flush = async () => {
      const aggregateValue = bucketValues.length
            ? await aggregate(bucketValues)
            : this.initValue;
      datapoints.push(new Datapoint(currentStart, aggregateValue));
      bucketValues = [];
    };

    for (const dp of this.series) {
      while (dp.timestamp >= currentStart + duration) {
        await flush();
        currentStart += duration;
      }
      bucketValues.push(dp.value);
    }

    await flush();

    return new DatapointSeries(datapoints, this.initValue);
  }

  async bucketizeMonths(
    months: number,
    aggregate: (values: number[]) => Promise<number>
  ): Promise<DatapointSeries> {
    if (!Number.isInteger(months) || months <= 0) {
      throw new Error("Bucket size (months) must be a positive integer");
    }
    if (this.isEmpty()) {
      return new DatapointSeries([], this.initValue);
    }

    const firstTimestamp = this.series[0].timestamp;
    const firstDate = new Date(firstTimestamp);
    const monthIndex = Math.floor(firstDate.getUTCMonth() / months);
    let currentStart = addMonths(startOfYear(firstTimestamp), monthIndex * months);
    let nextStart = addMonths(currentStart, months);

    const datapoints: Datapoint[] = [];
    let bucketValues: number[] = [];

    const flush = async () => {
      const aggregateValue = bucketValues.length
        ? await aggregate(bucketValues)
        : this.initValue;
      datapoints.push(new Datapoint(currentStart, aggregateValue));
      bucketValues = [];
    };

    for (const dp of this.series) {
      while (dp.timestamp >= nextStart) {
        await flush();
        currentStart = nextStart;
        nextStart = addMonths(currentStart, months);
      }
      bucketValues.push(dp.value);
    }

    await flush();

    return new DatapointSeries(datapoints, this.initValue);
  }
}
