# Impulses TypeScript SDK

Type-safe client for interacting with an Impulses server from Node.js or modern browsers.  
This package mirrors the Python SDK’s functionality—fetching, uploading, and transforming datapoints with fluent operations.

---

## 1. Getting started

```bash
# from repo root
cd client-sdks/typescript
npm install        # installs TypeScript + runtime deps
npm run build      # emits dist/ with CJS + declarations
```

To use it inside another app without publishing, rely on a relative path install:

```bash
cd /path/to/your/app
npm install ../impulses/client-sdks/typescript
```

Or add via `package.json`:

```json
"dependencies": {
  "@impulses/sdk-typescript": "file:../impulses/client-sdks/typescript"
}
```

---

## 2. Usage

```ts
import {
  ImpulsesClient,
  Datapoint,
  DatapointSeries,
  COMMON_LIBRARY,
  compute,
  format as formatPulseLang,
} from "@impulses/sdk-typescript";

const client = new ImpulsesClient({
  url: "http://localhost:8080",
  tokenValue: "your-token-here",
  timeoutMs: 5000,
});

// Fetch metrics
const metrics = await client.listMetricNames();

// Upload datapoints
const datapoints = new DatapointSeries([
  new Datapoint(Date.now(), 42, { env: "test" }),
]);
await client.uploadDatapoints("transactions", datapoints);

// Fetch and run fluent ops
const deltas = await client.fetchDatapoints("transactions");
const expenses = deltas
  .filter((dp) => dp.value < 0)
  .map((dp) => new Datapoint(dp.timestamp, -dp.value, dp.dimensions));
const expenses30d = expenses.slidingWindow(30, (values) =>
  values.reduce((sum, v) => sum + v, 0)
);

### PulseLang programs

The SDK also embeds the PulseLang interpreter so you can derive streams declaratively:

```ts
const library = COMMON_LIBRARY; // optional helpers (prefix-sum, buckets, EMA, etc.)

const program = `
  (define deltas (data "transactions"))
  (define sum (aggregate-from +))
  (define expenses (filter deltas (< 0)))
  (define expenses-30d (window expenses "30d" sum))
`;

const streams = await compute(client, library, program);
const expenses30d = streams.get("expenses-30d");
```

Need to clean up a PulseLang script before saving it? Use the formatter (note that currently it just writes the program from AST and doesn't preserve any custom spacing or comments):

```ts
const pretty = formatPulseLang(program);
```

See [`docs/PulseLang.md`](../../docs/PulseLang.md) for the complete language guide, built-in reference, and testing instructions.
```
