import { createContext, useContext, useState, useEffect } from 'react';
import { api } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  async function checkAuth() {
    try {
      const userData = await api.getCurrentUser();
      setUser(userData);
    } catch (err) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  async function login(email, password) {
    const response = await api.login(email, password);
    setUser(response.user);
    return response;
  }

  async function logout() {
    await api.logout();
    setUser(null);
  }

  async function signup(email, password, role) {
    const response = await api.signup(email, password, role);
    return response;
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, signup, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
