import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import Metrics from './pages/Metrics';
import MetricDetail from './pages/MetricDetail';
import Tokens from './pages/Tokens';
import Charts from './pages/Charts';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  
  if (loading) {
    return <div className="loading">Loading...</div>;
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth();
  
  if (loading) {
    return <div className="loading">Loading...</div>;
  }
  
  if (user) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return children;
}

function Navigation() {
  const { user, logout } = useAuth();
  
  if (!user) return null;
  
  return (
    <nav className="nav">
      <Link to="/dashboard">Dashboard</Link>
      <Link to="/metrics">Metrics</Link>
      <Link to="/tokens">Tokens</Link>
      <Link to="/charts">Charts</Link>
      <button onClick={logout} style={{ float: 'right' }}>Logout</button>
    </nav>
  );
}

function AppContent() {
  return (
    <>
      <h1>Impulses</h1>
      <Navigation />
      <Routes>
        <Route path="/login" element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        } />
        <Route path="/signup" element={
          <PublicRoute>
            <Signup />
          </PublicRoute>
        } />
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } />
        <Route path="/metrics" element={
          <ProtectedRoute>
            <Metrics />
          </ProtectedRoute>
        } />
        <Route path="/metrics/:name" element={
          <ProtectedRoute>
            <MetricDetail />
          </ProtectedRoute>
        } />
        <Route path="/tokens" element={
          <ProtectedRoute>
            <Tokens />
          </ProtectedRoute>
        } />
        <Route path="/charts" element={
          <ProtectedRoute>
            <Charts />
          </ProtectedRoute>
        } />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  );
}
