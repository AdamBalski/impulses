import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import { AppWebSocketProvider } from './contexts/AppWebSocketContext';
import { UserSettingsProvider } from './contexts/UserSettingsContext';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import Metrics from './pages/Metrics';
import MetricDetail from './pages/MetricDetail';
import Tokens from './pages/Tokens';
import GCalIntegration from './pages/GCalIntegration';
import Charts from './pages/Charts';
import Dashboards from './pages/Dashboards';
import LocalStorageSync from './pages/LocalStorageSync';
import Settings from './pages/Settings';
import Chat from './pages/Chat';
import LlmModels from './pages/LlmModels';

const BASENAME = import.meta.env.BASE_URL.replace(/\/$/, '');
const FAVICON_URL = `${import.meta.env.BASE_URL}favicon.svg`;

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
      <div className="nav-links">
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/metrics">Metrics</Link>
        <Link to="/tokens">Tokens</Link>
        <Link to="/gcal">GCal integration</Link>
        <Link to="/dashboards">Dashboards</Link>
        <Link to="/charts">Charts</Link>
        <Link to="/chat">Chat</Link>
        <Link to="/models">Models</Link>
        <Link to="/storage-sync">Storage Sync</Link>
        <Link to="/settings">Settings</Link>
      </div>
      <button className="nav-logout" onClick={logout}>Logout</button>
    </nav>
  );
}

function AppContent() {
  return (
    <>
      <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <img src={FAVICON_URL} alt="Impulses logo" width="64" height="64" />
        Impulses
      </h1>
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
        <Route path="/gcal" element={
          <ProtectedRoute>
            <GCalIntegration />
          </ProtectedRoute>
        } />
        <Route path="/charts" element={
          <ProtectedRoute>
            <Charts />
          </ProtectedRoute>
        } />
        <Route path="/charts/:chartId" element={
          <ProtectedRoute>
            <Charts />
          </ProtectedRoute>
        } />
        <Route path="/dashboards" element={
          <ProtectedRoute>
            <Dashboards />
          </ProtectedRoute>
        } />
        <Route path="/dashboards/:dashboardId" element={
          <ProtectedRoute>
            <Dashboards />
          </ProtectedRoute>
        } />
        <Route path="/storage-sync" element={
          <ProtectedRoute>
            <LocalStorageSync />
          </ProtectedRoute>
        } />
        <Route path="/chat" element={
          <ProtectedRoute>
            <Chat />
          </ProtectedRoute>
        } />
        <Route path="/chat/:chatId" element={
          <ProtectedRoute>
            <Chat />
          </ProtectedRoute>
        } />
        <Route path="/models" element={
          <ProtectedRoute>
            <LlmModels />
          </ProtectedRoute>
        } />
        <Route path="/settings" element={
          <ProtectedRoute>
            <Settings />
          </ProtectedRoute>
        } />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
      <div style={{ height: '30px' }}></div>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter basename={BASENAME}>
      <AuthProvider>
        <AppWebSocketProvider>
          <UserSettingsProvider>
            <AppContent />
          </UserSettingsProvider>
        </AppWebSocketProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
