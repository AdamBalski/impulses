# PulseLang

PulseLang is Impulses' declarative stream-computation language. It uses an S-expression syntax alongside Impulses data streams so you can stitch together derived metrics, rolling aggregates, and predicates without touching server code.

## Quick start

```lisp
(define deltas (data "transactions"))

(define sum (aggregate-from +))
(define expenses (filter deltas (< 0)))
(define income   (filter deltas (>= 0)))

(define expenses-30d (window expenses "30d" sum))
(define income-30d   (window income "30d" sum))
(define runway
  (compose (prefix deltas sum)
       expenses-30d
       (lambda (balance expense)
         (/ balance (* 30 expense)))))
```

Evaluate scripts through the TypeScript SDK:

```ts
import { ImpulsesClient, compute } from "@impulses/sdk-typescript";

const client = new ImpulsesClient({ url, tokenValue });
const streams = await compute(client, pulseLangProgram);
const expenses30d = streams.get("expenses-30d");
```

See `tests/dsl/interpreter.test.ts` for a Vitest example using mocked streams.

## Syntax

PulseLang programs are S-expressions. Each expression is either a literal, a symbol, or a list where the first element names a function. Variables live in lexical scopes created with `lambda` and `define`.

### Literals
- Numbers: `42`, `-3.14`
- Strings: `"foo"`
- Streams: returned via `data`, `window`, `prefix`, etc.

### Special forms
- `(define name expr)` — bind `name` in the current scope.
- `(lambda (arg1 arg2 ...) body...)` — create a function capturing the current environment.

## Built-ins

PulseLang ships with a runtime environment that matches the TypeScript interpreter in `client-sdks/typescript/src/dsl/interpreter.ts`. Everything below is available without importing any extra libraries.

### Stream helpers
- `(data name)` — fetch a remote metric stream via the SDK client (calls `ImpulsesClient.fetchDatapoints` under the hood). Streams are cached by name per runtime.
- `(window stream duration aggregate)` — rolling window evaluation. The duration string is parsed by `parseDuration` and accepts suffixes like `ms`, `s`, `min`, `h`, `d`.
- `(prefix stream aggregate)` — accumulate values using the stream’s initial value as the seed.
- `(bucketize stream duration aggregate)` — group datapoints into fixed windows, then aggregate each bucket. Helpers like `buckets` and `buckets-count` in the common library wrap this.
- `(filter stream predicate)` — keep datapoints when the predicate returns truthy. Predicate receives `(value datapoint)`.
- `(map stream fn1 fn2 ...)` — sequentially apply mapper functions. A mapper may return either a raw number or a full datapoint.
- `(compose stream1 stream2 ... aggregate)` — merge multiple streams on timestamp and feed the aligned values to an aggregate lambda.

### Logical & predicates
- `(not predicate)` inverts the predicate result.
- `(and pred...)`, `(or pred...)` short-circuit over predicate lambdas.
- Comparators `<`, `<=`, `=`, `>=`, `>` behave either as binary functions or as predicate builders when partially applied.
- Dimension predicates:
  - `(dimension-is key value)` tests for equality on a dimension string.
  - `(dim-matches key regex)` uses JavaScript regular expressions for pattern matching.
  - `(no-dimension key)` checks that a dimension is absent.

### Arithmetic
`+` and `*` accept one or more numbers. `-` and `/` are binary. `exp` computes exponentiation, `abs` returns absolute value, and `sgn` returns the numeric sign.

### Aggregates
Aggregates always consume a list of numbers and return a number:
- `(aggregate-from binary-fn)` — folds using a user-provided binary lambda.
- `(p percent)` — percentile 0–100.
- Built-ins: `count`, `sum`, `avg`, `min`, `max`, `std`.

### Common library helpers
The TypeScript SDK exports `COMMON_LIBRARY`, a PulseLang snippet that defines:
- Duration aliases: `MINUTE`, `HOUR`, `DAY`, `WEEK`, `MONTH`, `YEAR`.
- Prefix helpers: `prefix-sum`, `prefix-count`.
- Basic filters: `positive`, `negative`.
- Scaling helpers: `scale`, `multiply`.
- Window helpers: `sum-window`, `count-window`.
- Bucket helpers: `buckets`, `buckets-count`.
- `ema` (exponential moving average) built on `prefix` and `aggregate-from`.
Call `compute(client, COMMON_LIBRARY, program)` to preload these helpers before evaluating your program.

## Runtime API

| Function | Description |
| --- | --- |
| `compute(client, library, program)` | Evaluates `library` (e.g., `COMMON_LIBRARY`) followed by `program`, using the provided `ImpulsesClient` as the `data` resolver. Returns `Map<string, DatapointSeries>` containing all top-level bindings that are streams. |

## Error handling
- Unknown symbols throw `Undefined symbol` errors.
- Duration parsing rejects zero/unknown units.
- Built-ins validate argument types (e.g., `window` requires a stream and aggregate function).

## Testing
PulseLang evaluation is covered by `tests/dsl/interpreter.test.ts`, which uses Vitest and synthetic streams to assert that the DSL produces expected series. Run `npm run test` inside `client-sdks/typescript/` while iterating on the interpreter or docs.
