import { ImpulsesClient } from '@impulses/sdk-typescript';

const API_BASE = import.meta.env.VITE_API_URL
  ? import.meta.env.VITE_API_URL
  : '/api';

let cachedClient = null;
let cachedSignature = null;

function getStoredToken() {
  return localStorage.getItem('impulses_token') || '';
}

export function getImpulsesClient() {
  const token = getStoredToken();
  if (!token) {
    throw new Error('Missing data token. Please configure a token first.');
  }

  const signature = `${API_BASE}::${token}`;
  if (cachedClient && cachedSignature === signature) {
    return cachedClient;
  }

  cachedClient = new ImpulsesClient({
    url: API_BASE,
    tokenValue: token,
  });
  cachedSignature = signature;
  return cachedClient;
}
