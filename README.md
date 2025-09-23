# Impulses Project

## 1. Overview
Impulses is a system for tracking user-defined metrics, storing them persistently, and providing analytics via a client SDK.  
Main components include the server, background jobs, Google Calendar integration, and the client SDK.

---

## 2. Related Documentation
| Doc | Description |
|-----|-------------|
| [Server README](server/README.md) | How to deploy and run the server, environment variables, token setup, OAuth2 setup. |
| [Client SDK README](client-sdk/README.md) | How to install and use the client SDK, operations like `map`, `filter`, `sliding_window`. |
| [GCal Polling Job](server/G_CAL_POLLING_JOB.md) | Details on the background job fetching events from Google Calendar and converting them into metrics. |

---

## 3. Deployment Options
Impulses can be deployed in three ways, look ([here](server/README.md)):
- **Local Deployment**  
  Run directly from a development environment using Python virtual environments. Useful for testing or development.
- **Deploy via `deploy.sh`**  
  Directly executes the deployment script on a target remote host via SSH.
- **Deploy via GitHub Actions**  
  The GitHub Action workflow triggers `deploy.sh` on the specified remote host automatically.

---

## 4. Impulses SDK Quick Show-Off
Example using the SDK to fetch, filter, and transform metric data (for more, look [here](client-sdk/README.md)):

```python
from impulses_sdk import client
from impulses_sdk import operations

# Connect to the server
remote = ImpulsesClient("http://localhost:8080", "your-token")

# Fetch transaction deltas
deltas = remote.fetch_datapoints("transactions")

# Compute prefix sum (real account balance)
acc = impulse_ops.prefix_op(deltas, sum)

# Separate expenses and income
expenses = deltas.filter(lambda dp: dp.value < 0)
income = deltas.filter(lambda dp: dp.value >= 0)

# Compute 30-day sliding window sum
expenses_30d = impulse_ops.sliding_window(expenses, 30, sum)
income_30d = impulse_ops.sliding_window(income, 30, sum)
```
---
