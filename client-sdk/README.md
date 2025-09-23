# Impulses Client SDK Usage & Operations Guide

The `impulses_sdk` allows you to interact with an Impulses server, fetch metrics, upload datapoints, and perform time-series operations on them.

---

## Installation

Clone the repo and if your client code is in a different directory than the SDK, install it using `pip` in editable mode:

```bash
cd /path/to/client-sdk
git clone https://github.com/AdamBalski/impulses ./path/to/your/impulses
python3 -m venv venv
source venv/bin/activate
pip install -e ./path/to/your/impulses/client-sdk
```

This ensures your client code can import `impulses_sdk` while keeping it editable for local updates.

---

## Connecting to the Server

Initialize the client with the server URL and authentication token (both required):

```python
from impulses_sdk.client import ImpulsesClient

client = ImpulsesClient(
    url="https://my-impulses-server.com",
    token="YOUR_X_TOKEN_HERE"
)
```

**Notes:**

- The token must match the X-Token expected by the server.  
- The SDK uses HTTP requests internally (`GET`, `POST`, `DELETE`) to access metrics.  

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

## Time-Series Operations

The SDK provides operations on `DatapointSeries` for analytics.

### 1. Filter

Filter data points based on a predicate

```python
expenses = deltas.filter(lambda dp: dp.value < 0)
```

### 2. Map

Map all data points

```python
positive_expenses = expenses.map(lambda dp: Datapoint(dp.timestamp, -dp.value))
```
### 3. Prefix Operation (Cumulative)

```python
from impulses_sdk import operations

deltas = client.fetch_datapoints("transactions")
acc = operations.prefix_op(deltas, sum)  # cumulative sum
```

### 4. Sliding Window

```python
expenses = deltas.filter(lambda dp: dp.value < 0)
expenses_30d = operations.sliding_window(expenses, 30, sum)
```

- `window`: length of window in time units
- `operation`: function applied to all values in the window (e.g., `sum`, `statistics.stdev`)  
- `fluid_phase_out` (optional): whether to phase out old values after window end  

### 5. Compose Impulses

Combine multiple series with a custom operation:

```python
safe_division = lambda vals: vals[0] / max(vals[1], 0.1)
runway = operations.compose_impulses([acc, expenses_30d], safe_division)
```

- Returns a new `DatapointSeries` computed from multiple input series after applying an operation.

###
---

## Example: Cashflow Analysis

```python
from impulses_sdk.client import ImpulsesClient
from impulses_sdk import operations

client = ImpulsesClient(
    url="https://my-impulses-server.com",
    token="YOUR_X_TOKEN_HERE"
)

deltas = client.fetch_datapoints("transactions")

expenses = deltas.filter(lambda dp: dp.value < 0)
income = deltas.filter(lambda dp: dp.value >= 0)

expenses_30d = operations.sliding_window(expenses, 30, sum)
income_30d = operations.sliding_window(income, 30, sum)

def savings_rate(vals):
    income_sum = sum(v for v in vals if v > 0)
    expense_sum = sum(-v for v in vals if v < 0)
    if income_sum + expense_sum == 0:
        return 0
    return (income_sum - expense_sum) / (income_sum + expense_sum)

savings_rate_30d = operations.sliding_window(deltas, 30, savings_rate)
```

This gets you several impulses:
* transactions (`deltas`)
* expenses
* income
* sum of expenses over 30 days
* sum of income over 30 days
* a rolling 30-day savings rate from raw transaction deltas

---
