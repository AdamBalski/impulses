import { ConstantImpulse, Datapoint, DatapointSeries, EvaluatedImpulse } from "./models.js";
import { MinHeap } from "./internal/minHeap.js";

interface HeapEntry {
  time: number;
  value: number;
  idx: number;
}

export async function composeImpulses(
  impulses: EvaluatedImpulse[],
  operation: (values: number[]) => Promise<number> | number
): Promise<DatapointSeries> {
  if (impulses.length === 0) {
    return new DatapointSeries();
  }

  const indices = new Array(impulses.length).fill(0);
  const lastValues = impulses.map((impulse) => impulse.getInitVal());
  const initValue = await Promise.resolve(operation([...lastValues]));

  const heap = new MinHeap<HeapEntry>((a, b) => a.time - b.time);
  let hasSeries = false;

  impulses.forEach((impulse, idx) => {
    if (impulse.isConstant()) {
      return;
    }

    const series = impulse.asDatapointSeries();
    if (series.length === 0) {
      return;
    }

    hasSeries = true;
    heap.push({
      time: series.timeAt(0),
      value: series.valueAt(0),
      idx,
    });
  });

  if (!hasSeries) {
    return new DatapointSeries([], initValue);
  }

  const datapointSeriesCache = impulses.map((impulse) =>
    impulse.isConstant() ? null : impulse.asDatapointSeries()
  );

  const maybePushFrom = (seriesIdx: number) => {
    const series = datapointSeriesCache[seriesIdx];
    if (!series) {
      return;
    }

    indices[seriesIdx] += 1;
    if (indices[seriesIdx] < series.length) {
      const next = series.series[indices[seriesIdx]];
      heap.push({
        time: next.timestamp,
        value: next.value,
        idx: seriesIdx,
      });
    }
  };

  const head = heap.peek();
  if (!head) {
    return new DatapointSeries([], initValue);
  }

  let currentTime = head.time;
  const result: Datapoint[] = [];

  const flush = async (nextTime: number) => {
    const value = await Promise.resolve(operation([...lastValues]));
    result.push(new Datapoint(currentTime, value));
    currentTime = nextTime;
  };

  let lastTime = currentTime;
  while (heap.size > 0) {
    const entry = heap.pop()!;
    lastTime = entry.time;
    maybePushFrom(entry.idx);
    if (entry.time > currentTime) {
      await flush(entry.time);
    }
    lastValues[entry.idx] = entry.value;
  }

  await flush(lastTime);

  return new DatapointSeries(result, initValue);
}
