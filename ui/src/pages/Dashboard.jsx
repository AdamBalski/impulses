import { useAuth } from '../AuthContext';
import { Link } from 'react-router-dom';

export default function Dashboard() {
  const { user } = useAuth();

  return (
    <div>
      <h2>Dashboard</h2>
      <p>Welcome, <strong>{user.email}</strong></p>
      <p>Role: <strong>{user.role}</strong></p>

      <div className="card">
        <h3>What is Impulses?</h3>
        <p>
          Impulses is a system for tracking user-defined metrics. Store datapoints,
          query them, and analyze trends over time.
        </p>
        <p>
          Use the Python SDK to perform operations like filter, map, sliding window,
          and prefix operations on your metric data.
        </p>
      </div>

      <div className="card">
        <h3>Quick Start</h3>
        <ol>
          <li><Link to="/tokens">Create a SUPER token</Link> and save it for metrics use</li>
          <li><Link to="/metrics">View your metrics</Link> or add new datapoints</li>
          <li>Use the Python SDK with your token to fetch and analyze data</li>
        </ol>
        <p><strong>Note:</strong> The Metrics page requires a SUPER token to be stored. Create one in the Tokens page and click "Save for Metrics Use".</p>
      </div>

      <div className="card">
        <h3>Example Usage</h3>
        <pre><code>{`from impulses_sdk import ImpulsesClient
from impulses_sdk import operations

# Connect
client = ImpulsesClient("http://localhost:8000", "your-token")

# Fetch data
deltas = client.fetch_datapoints("transactions")

# Compute prefix sum
balance = operations.prefix_op(deltas, sum)

# Filter
expenses = deltas.filter(lambda dp: dp.value < 0)

# Sliding window (30 days)
expenses_30d = operations.sliding_window(expenses, 30, sum)`}</code></pre>
      </div>
    </div>
  );
}
