# Impulses Client SDK Usage & Operations Guide

The `impulses_sdk` allows you to interact with an Impulses server, fetch metrics, upload datapoints, and perform time-series operations on them.

---

## Installation

Clone the repo and if your client code is in a different directory than the SDK, install it using `pip`:

```bash
git clone https://github.com/AdamBalski/impulses ./path/to/your/impulses
python3 -m venv venv
source venv/bin/activate
pip install -e ./path/to/your/impulses/client-sdk
```

This ensures your client code can import `impulses_sdk` while keeping it editable for local updates.

---

## Connecting to the Server

Initialize the client with the server URL and data token credentials:

```python
from impulses_sdk import ImpulsesClient

client = ImpulsesClient(
    url="http://localhost:8000",
    token_value="abc123xyz456",
    timeout=3  # optional, default 3 seconds
)
```

**Parameters:**

- `url`: Base URL of your Impulses server
- `token_value`: Plaintext value of the token (returned when created)
- `timeout`: Request timeout in seconds (optional, default: 30)

**Notes:**

- The token must have appropriate capability (API, INGEST, or SUPER)
- The SDK uses the `X-Data-Token` header format: `<name>:<plaintext>`
- All methods raise specific exceptions on errors (see Exception Handling)  

---

## Basic Operations

### Listing Metrics

```python
metric_names = client.list_metric_names()
print(metric_names)
```

### Fetching Datapoints

```python
from impulses_sdk import models

series = client.fetch_datapoints("transactions")  # returns DatapointSeries
for dp in series:
    print(dp.timestamp, dp.value)
```

### Uploading Datapoints

```python
datapoints = models.DatapointSeries([
    models.Datapoint(timestamp=1690000000, value=100.0)
])
client.upload_datapoints("transactions", datapoints)
```

### Deleting a Metric

```python
client.delete_metric_name("transactions")
```

---

## Exception Handling

The SDK provides comprehensive exception handling with specific exception types:

### Exception Types

| Exception | HTTP Status | Description |
|-----------|-------------|-------------|
| `AuthenticationError` | 401 | Invalid or expired token |
| `AuthorizationError` | 403 | Insufficient capability for operation |
| `NotFoundError` | 404 | Metric or resource not found |
| `ValidationError` | 422 | Invalid input (e.g., malformed datapoints) |
| `ServerError` | 5xx | Server-side error |
| `NetworkError` | N/A | Connection timeout or network failure |
| `ImpulsesError` | Any | Base exception (catch-all) |

**All exceptions inherit from `ImpulsesError`**, so you can catch it as a base class:

```python
try:
    client.upload_datapoints("metric", series)
except ImpulsesError as e:
    # Catches all SDK-related errors
    print(f"Operation failed: {e}")
```

---

## Time-Series Operations

The SDK provides fluent operations on `DatapointSeries` for analytics.

### 1. Filter

Filter data points based on a predicate

```python
expenses = deltas.filter(lambda dp: dp.value < 0)
```

### 2. Map

Transform all data points

```python
from impulses_sdk import Datapoint

positive_expenses = expenses.map(lambda dp: Datapoint(dp.timestamp, -dp.value, dp.dimensions))
```

### 3. Prefix Operation (Cumulative)

```python
deltas = client.fetch_datapoints("transactions")
acc = deltas.prefix_op(sum)  # cumulative sum
```

### 4. Sliding Window

```python
expenses = deltas.filter(lambda dp: dp.value < 0)
expenses_30d = expenses.sliding_window(30, sum)

# With custom operation
import statistics
avg_7d = series.sliding_window(7, statistics.mean)
```

**Parameters:**
- `window`: length of window in time units
- `operation`: function applied to all values in the window (e.g., `sum`, `statistics.mean`, `max`)  
- `fluid_phase_out` (optional): whether to phase out old values after window end (default: `True`)

### 5. Compose Impulses

Combine multiple series with a custom operation:

```python
from impulses_sdk import operations

safe_division = lambda vals: vals[0] / max(vals[1], 0.1)
runway = operations.compose_impulses([acc, expenses_30d], safe_division)
```

- Returns a new `DatapointSeries` computed from multiple input series after applying an operation.

### Method Chaining

All operations return `DatapointSeries`, enabling fluent method chaining:

```python
result = (client.fetch_datapoints("transactions")
    .filter(lambda dp: dp.value < 0)  # Only expenses
    .map(lambda dp: Datapoint(dp.timestamp, -dp.value, dp.dimensions))  # Make positive
    .sliding_window(30, sum)  # 30-day rolling sum
    .prefix_op(sum))  # Cumulative sum
```

---

## Example: Cashflow Analysis

### Using Fluent API

```python
from impulses_sdk import ImpulsesClient

client = ImpulsesClient(
    url="http://localhost:8000",
    token_value="your-token-plaintext-here"
)

# Fetch raw transaction data
deltas = client.fetch_datapoints("transactions")

# Filter expenses and income
expenses = deltas.filter(lambda dp: dp.value < 0)
income = deltas.filter(lambda dp: dp.value >= 0)

# Calculate 30-day rolling sums using fluent API
expenses_30d = expenses.sliding_window(30, sum)
income_30d = income.sliding_window(30, sum)

# Custom savings rate calculation
def savings_rate(vals):
    income_sum = sum(v for v in vals if v > 0)
    expense_sum = sum(-v for v in vals if v < 0)
    if income_sum + expense_sum == 0:
        return 0
    return (income_sum - expense_sum) / (income_sum + expense_sum)

savings_rate_30d = deltas.sliding_window(30, savings_rate)

# Cumulative account balance
acc = deltas.prefix_op(sum)
```

### Method Chaining Example

```python
# Calculate cumulative positive expenses over 30-day windows
positive_cumulative_expenses = (deltas
    .filter(lambda dp: dp.value < 0)  # Only expenses
    .map(lambda dp: Datapoint(dp.timestamp, -dp.value, dp.dimensions))  # Make positive
    .sliding_window(30, sum)  # 30-day rolling sum
    .prefix_op(sum))  # Cumulative
```

This fluent API gives you:
* **Raw transactions** (`deltas`)
* **Filtered data** (expenses, income)
* **Rolling windows** (30-day sums)
* **Cumulative values** (account balance)
* **Custom metrics** (savings rate)

All with clean, chainable method calls!

---
