const API_BASE = import.meta.env.VITE_API_URL 
  ? import.meta.env.VITE_API_URL 
  : '/api';

function getStoredToken() {
  return localStorage.getItem('impulses_token');
}

function getDataHeaders() {
  const token = getStoredToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['X-Data-Token'] = token;
  }
  return headers;
}

class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}
const includeCredentials = 'include';

async function handleResponse(response) {
  if (response.ok) {
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      const text = await response.text();
      if (!text || text.trim() === '') {
        return null;
      }
      try {
        return JSON.parse(text);
      } catch (e) {
        console.error('Failed to parse success response:', text);
        return null;
      }
    }
    return null;
  }
  
  let errorData = null;
  try {
    const text = await response.text();
    if (text && text.trim() !== '') {
      errorData = JSON.parse(text);
    }
  } catch (e) {
    console.error('Failed to parse error response:', e);
  }
  
  const errorMessage = errorData?.detail || errorData?.message || `HTTP ${response.status}`;
  throw new ApiError(
    errorMessage,
    response.status,
    errorData
  );
}

export const api = {
  async login(email, password) {
    try {
      const response = await fetch(`${API_BASE}/user/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: includeCredentials,
        body: JSON.stringify({ email, password })
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  },

  async logout() {
    try {
      const response = await fetch(`${API_BASE}/user/logout`, {
        method: 'POST',
        credentials: includeCredentials
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  },

  async signup(email, password, role = 'STANDARD') {
    try {
      const response = await fetch(`${API_BASE}/user`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: includeCredentials,
        body: JSON.stringify({ email, password, role })
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  },

  async getCurrentUser() {
    try {
      const response = await fetch(`${API_BASE}/user`, {
        credentials: includeCredentials
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  },

  async listMetrics() {
    try {
      const response = await fetch(`${API_BASE}/data`, {
        headers: getDataHeaders(),
        credentials: includeCredentials
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  },

  async getMetric(metricName) {
    try {
      const response = await fetch(`${API_BASE}/data/${encodeURIComponent(metricName)}`, {
        headers: getDataHeaders(),
        credentials: includeCredentials
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  },

  async addDatapoints(metricName, datapoints) {
    try {
      const response = await fetch(`${API_BASE}/data/${encodeURIComponent(metricName)}`, {
        method: 'POST',
        headers: getDataHeaders(),
        credentials: includeCredentials,
        body: JSON.stringify(datapoints)
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  },

  async deleteMetric(metricName) {
    try {
      const response = await fetch(`${API_BASE}/data/${encodeURIComponent(metricName)}`, {
        method: 'DELETE',
        headers: getDataHeaders(),
        credentials: includeCredentials
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  },

  async listTokens() {
    try {
      const response = await fetch(`${API_BASE}/token`, {
        credentials: includeCredentials
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  },

  async createToken(name, capability, expiresAt = null) {
    try {
      const response = await fetch(`${API_BASE}/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: includeCredentials,
        body: JSON.stringify({ name, capability, expires_at: expiresAt })
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  },

  async deleteToken(tokenId) {
    try {
      const response = await fetch(`${API_BASE}/token/${tokenId}`, {
        method: 'DELETE',
        credentials: includeCredentials
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  },

  async startGoogleOAuthFlow(token) {
    var body;
    try {
      const response = await fetch(`${API_BASE}/oauth2/google/auth`, {
        headers: {
          'X-Data-Token': token
        },
        credentials: includeCredentials,
      });
      body = await handleResponse(response);
    } catch (err) {
      console.error('OAuth flow error:', err);
      throw new ApiError('Failed to start Google OAuth flow', 0, null);
    }

    const url = body?.url;
    if (!url) {
      throw new ApiError('OAuth flow error: missing authorization url', 0, body);
    }

    window.location.href = url;
  },

  async listGoogleOAuthConfigs() {
    try {
      const response = await fetch(`${API_BASE}/oauth2/google/configs`, {
        headers: getDataHeaders(),
        credentials: includeCredentials,
      });
      return handleResponse(response);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error: Unable to connect to server', 0, null);
    }
  }
};

export { ApiError };
