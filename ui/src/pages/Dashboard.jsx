import { useAuth } from '../AuthContext';
import { Link } from 'react-router-dom';

const TYPESCRIPT_SDK_URL = 'https://github.com/AdamBalski/impulses/tree/main/client-sdks/typescript';
const PYTHON_SDK_URL = 'https://github.com/AdamBalski/impulses/tree/main/client-sdks/python3';

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
          Impulses is a personal metrics and analysis system. It is meant for collecting
          streams of datapoints, querying them later, and building derived views over them
          with charts, dashboards, and PulseLang.
        </p>
        <p>
          A metric is just a named stream of timestamped numeric datapoints with arbitrary
          string dimensions. That means you can store things like transactions, balances,
          weights, steps, latency samples, event counters, or any other time-series data
          you want to inspect later.
        </p>
      </div>

      <div className="card">
        <h3>Tokens</h3>
        <p>
          Tokens are required for all API and SDK access. If you want to ingest data,
          fetch metrics, or use the SDKs, create a token first in{' '}
          <Link to="/settings/tokens">Settings → Tokens</Link>.
        </p>
        <p>
          For metrics work in the UI, create a <strong>SUPER</strong> token and save it
          for metrics use.
        </p>
      </div>

      <div className="card">
        <h3>Metrics</h3>
        <p>
          Metrics are your raw stored data. Each metric is a named stream of datapoints,
          and each datapoint has a timestamp, a numeric value, and optional dimensions.
        </p>
        <p>
          Use <Link to="/metrics">Metrics</Link> to inspect stored streams and add new
          datapoints manually.
        </p>
      </div>

      <div className="card">
        <h3>Charts</h3>
        <p>
          Charts turn raw metrics into reusable visual definitions. A chart contains a
          PulseLang program plus rendering settings, so it can express filtered views,
          rolling windows, ratios, aggregates, and other derived series.
        </p>
        <p>
          Use <Link to="/charts">Charts</Link> to create, inspect, and edit those views.
        </p>
      </div>

      <div className="card">
        <h3>Dashboards</h3>
        <p>
          Dashboards arrange multiple charts into one layout. They are for combining
          related charts into one place so you can inspect a larger story at once.
        </p>
        <p>
          Use <Link to="/dashboards">Dashboards</Link> to build and browse those layouts.
        </p>
      </div>

      <div className="card">
        <h3>Chat</h3>
        <p>
          Chat is the read-only Pulse Wizard interface. It can inspect your saved charts,
          dashboards, metrics, and PulseLang definitions, and it can also propose charts
          visually for you to save.
        </p>
        <p>
          Use <Link to="/chat">Chat</Link> after configuring at least one model in{' '}
          <Link to="/settings/models">Settings → Models</Link>.
        </p>
      </div>

      <div className="card">
        <h3>SDKs</h3>
        <p>
          Use the SDKs to push data into Impulses and compute over it programmatically.
        </p>
        <ol>
          <li><a href={TYPESCRIPT_SDK_URL} target="_blank" rel="noreferrer">TypeScript SDK on GitHub</a></li>
          <li><a href={PYTHON_SDK_URL} target="_blank" rel="noreferrer">Python SDK on GitHub</a></li>
        </ol>
      </div>
    </div>
  );
}
