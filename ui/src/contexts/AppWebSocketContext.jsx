import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../AuthContext';
import { buildAppWebSocketUrl } from '../lib/wsUrl';

const AppWebSocketContext = createContext(null);
const RECONNECT_DELAY_MS = 2000;

function sendSocketJson(socket, payload) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return false;
  }
  socket.send(JSON.stringify(payload));
  return true;
}

async function executeLocalLlmRequest(socket, message) {
  const requestId = message.request_id;
  const url = typeof message.url === 'string' ? message.url : '';
  const method = typeof message.method === 'string' ? message.method : 'POST';
  const body = message.body;
  const headersList = Array.isArray(message.headers) ? message.headers : [];
  const headers = { 'Content-Type': 'application/json' };

  for (const header of headersList) {
    if (!header || typeof header.name !== 'string' || typeof header.value !== 'string') {
      continue;
    }
    headers[header.name] = header.value;
  }

  try {
    const response = await fetch(url, {
      method,
      headers,
      body: JSON.stringify(body),
    });

    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (response.ok) {
      sendSocketJson(socket, {
        type: 'llm_response',
        request_id: requestId,
        ok: true,
        status: response.status,
        data,
      });
      return;
    }

    let error = `Localhost model request failed with status ${response.status}`;
    if (data && typeof data === 'object') {
      const detail = data.error || data.detail || data.message;
      if (typeof detail === 'string' && detail.trim()) {
        error = detail.trim();
      } else if (detail && typeof detail === 'object' && typeof detail.message === 'string' && detail.message.trim()) {
        error = detail.message.trim();
      }
    }

    sendSocketJson(socket, {
      type: 'llm_response',
      request_id: requestId,
      ok: false,
      status: response.status,
      error,
    });
  } catch (err) {
    sendSocketJson(socket, {
      type: 'llm_response',
      request_id: requestId,
      ok: false,
      status: 0,
      error: err instanceof Error ? err.message : 'Failed to call localhost model endpoint',
    });
  }
}

export function AppWebSocketProvider({ children }) {
  const { user, loading } = useAuth();
  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const listenersRef = useRef(new Set());
  const [status, setStatus] = useState('disconnected');
  const [connectionMeta, setConnectionMeta] = useState(null);
  const [error, setError] = useState('');

  const subscribe = useCallback((listener) => {
    listenersRef.current.add(listener);
    return () => {
      listenersRef.current.delete(listener);
    };
  }, []);

  const sendChatMessage = useCallback(({ chatId, modelId, content }) => (
    sendSocketJson(socketRef.current, {
      type: 'chat_send',
      chat_id: chatId || null,
      model_id: modelId || null,
      content,
    })
  ), []);

  useEffect(() => {
    function clearReconnectTimer() {
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    }

    function cleanupSocket() {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    }

    if (loading) {
      return undefined;
    }

    if (!user) {
      clearReconnectTimer();
      cleanupSocket();
      setStatus('disconnected');
      setConnectionMeta(null);
      setError('');
      return undefined;
    }

    let cancelled = false;

    function scheduleReconnect() {
      if (cancelled) {
        return;
      }
      clearReconnectTimer();
      reconnectTimerRef.current = window.setTimeout(() => {
        connect();
      }, RECONNECT_DELAY_MS);
    }

    function connect() {
      if (cancelled) {
        return;
      }
      if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
        return;
      }

      setStatus('connecting');
      setError('');
      const socket = new WebSocket(buildAppWebSocketUrl('/ws/app'));
      socketRef.current = socket;

      socket.onopen = () => {
        if (cancelled) {
          socket.close();
          return;
        }
        setStatus('connected');
        setError('');
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'connected') {
            setConnectionMeta(message);
            return;
          }
          if (message.type === 'ping') {
            sendSocketJson(socket, { type: 'pong' });
            return;
          }
          if (message.type === 'llm_request') {
            executeLocalLlmRequest(socket, message);
            return;
          }
          listenersRef.current.forEach((listener) => {
            listener(message);
          });
        } catch {
          // ignore malformed frames
        }
      };

      socket.onclose = (event) => {
        if (cancelled) {
          return;
        }
        socketRef.current = null;
        setStatus('disconnected');
        setConnectionMeta(null);
        setError(
          event.reason
            ? `Websocket closed: ${event.reason} (code ${event.code})`
            : `Websocket closed (code ${event.code})`,
        );
        scheduleReconnect();
      };

      socket.onerror = () => {
        setStatus('error');
        setError('Websocket handshake failed or the server rejected the connection.');
      };
    }

    connect();

    return () => {
      cancelled = true;
      clearReconnectTimer();
      cleanupSocket();
      setConnectionMeta(null);
    };
  }, [user, loading]);

  const value = useMemo(() => ({
    status,
    error,
    connectionMeta,
    isConnected: status === 'connected',
    subscribe,
    sendChatMessage,
  }), [status, error, connectionMeta, subscribe, sendChatMessage]);

  return (
    <AppWebSocketContext.Provider value={value}>
      {children}
    </AppWebSocketContext.Provider>
  );
}

export function useAppWebSocket() {
  const context = useContext(AppWebSocketContext);
  if (!context) {
    throw new Error('useAppWebSocket must be used within AppWebSocketProvider');
  }
  return context;
}
