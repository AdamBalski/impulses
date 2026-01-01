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

The SDK exports ES2015 modules compiled to CommonJS with bundled type definitions.

---

## 2. Usage

```ts
import {
  ImpulsesClient,
  Datapoint,
  DatapointSeries,
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
```
