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

  filter(predicate: (dp: Datapoint) => boolean): DatapointSeries {
    return new DatapointSeries(
      this.series.filter(predicate),
      this.initValue
    );
  }

  map(mapper: (dp: Datapoint) => Datapoint): DatapointSeries {
    return new DatapointSeries(
      this.series.map(mapper),
      this.initValue
    );
  }

  prefixOp(operation: (values: number[]) => number): DatapointSeries {
    let prev = this.initValue;
    const nextSeries = this.series.map((dp) => {
      prev = operation([prev, dp.value]);
      return new Datapoint(dp.timestamp, prev, dp.dimensions);
    });
    const nextInit = operation([this.initValue]);
    return new DatapointSeries(nextSeries, nextInit);
  }

  slidingWindow(
    window: number,
    operation: (values: number[]) => number,
    fluidPhaseOut = true
  ): DatapointSeries {
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
    const result: Datapoint[] = [];

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
        result.push(new Datapoint(event.time, this.initValue));
        continue;
      }

      const values: number[] = [];
      counts.forEach((count, value) => {
        for (let i = 0; i < count; i += 1) {
          values.push(value);
        }
      });
      result.push(new Datapoint(event.time, operation(values)));
    }

    if (fluidPhaseOut && result.length > 0) {
      result.pop();
    }

    return new DatapointSeries(result, this.initValue);
  }
}
