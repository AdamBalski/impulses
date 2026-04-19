import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import Chart from '../components/Chart';
import ChatMarkdown from '../components/ChatMarkdown';
import { useAppWebSocket } from '../contexts/AppWebSocketContext';
import { loadAiChatSettings, saveAiChatSettings } from '../lib/aiChatSettings';
import {
  normalizeChart,
  normalizeDisplayChart,
  toChartBody,
  toDisplayChartMetadataJson,
  toDisplayChartMetadataPayload,
} from '../lib/visualizationModel';

const NEW_CHAT_VALUE = '__new__';
const PENDING_USER_ID = 'pending-user';
const PENDING_ASSISTANT_ID = 'pending-assistant';
const INITIAL_MESSAGES = [
  {
    id: 'intro',
    role: 'assistant',
    content: 'Pulse Wizard is ready. Pick a saved model, then ask about charts, dashboards, metrics, or PulseLang.',
    model_id: null,
    model: null,
    request_started_at: null,
    created_at: Date.now(),
    reasoning: null,
    display_charts: [],
  },
];

function sortByName(items) {
  return [...items].sort((a, b) => (a.model || '').localeCompare(b.model || ''));
}

function hasEquivalentUserMessage(messages, userMessage) {
  const requestStartedAt = userMessage?.request_started_at ?? userMessage?.created_at ?? null;
  const content = typeof userMessage?.content === 'string' ? userMessage.content : '';
  return messages.some((message) => (
    message?.role === 'user' &&
    (message.request_started_at ?? message.created_at ?? null) === requestStartedAt &&
    (message.content || '') === content
  ));
}

function normalizeMessageSequence(messages) {
  const deduped = [];
  const seenIds = new Set();

  for (const message of messages) {
    if (!message || typeof message !== 'object') {
      continue;
    }

    if (message.id && seenIds.has(message.id)) {
      continue;
    }

    if (message.role === 'user' && hasEquivalentUserMessage(deduped, message)) {
      const existingIndex = deduped.findIndex((item) => (
        item?.role === 'user' &&
        (item.request_started_at ?? item.created_at ?? null) === (message.request_started_at ?? message.created_at ?? null) &&
        (item.content || '') === (message.content || '')
      ));
      if (
        existingIndex >= 0 &&
        String(deduped[existingIndex].id || '').startsWith(PENDING_USER_ID) &&
        !String(message.id || '').startsWith(PENDING_USER_ID)
      ) {
        deduped[existingIndex] = message;
        if (message.id) {
          seenIds.add(message.id);
        }
      }
      continue;
    }

    deduped.push(message);
    if (message.id) {
      seenIds.add(message.id);
    }
  }

  deduped.sort((left, right) => {
    if (left.id === 'intro') {
      return -1;
    }
    if (right.id === 'intro') {
      return 1;
    }

    const leftRequest = left.request_started_at ?? left.created_at ?? 0;
    const rightRequest = right.request_started_at ?? right.created_at ?? 0;
    if (leftRequest !== rightRequest) {
      return leftRequest - rightRequest;
    }

    if (left.role !== right.role) {
      return left.role === 'user' ? -1 : 1;
    }

    const leftCreated = left.created_at ?? leftRequest;
    const rightCreated = right.created_at ?? rightRequest;
    if (leftCreated !== rightCreated) {
      return leftCreated - rightCreated;
    }

    return String(left.id || '').localeCompare(String(right.id || ''));
  });

  return deduped;
}

function normalizeMessages(messages) {
  if (!Array.isArray(messages) || messages.length === 0) {
    return INITIAL_MESSAGES;
  }
  return normalizeMessageSequence(messages);
}

function formatChatTitle(chat) {
  const title = typeof chat?.title === 'string' ? chat.title.trim() : '';
  if (title) {
    return title;
  }
  return '(untitled chat)';
}

function formatTimestamp(timestamp) {
  if (typeof timestamp !== 'number' || Number.isNaN(timestamp)) {
    return 'Unknown';
  }
  return new Date(timestamp).toLocaleString();
}

function formatDuration(milliseconds) {
  if (typeof milliseconds !== 'number' || Number.isNaN(milliseconds) || milliseconds < 0) {
    return 'Unknown';
  }
  if (milliseconds < 1000) {
    return `${milliseconds} ms`;
  }
  const seconds = milliseconds / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(seconds < 10 ? 1 : 0)} s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

function formatJson(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function buildLineDiff(beforeText, afterText) {
  const beforeLines = String(beforeText || '').split('\n');
  const afterLines = String(afterText || '').split('\n');
  const dp = Array.from({ length: beforeLines.length + 1 }, () => Array(afterLines.length + 1).fill(0));

  for (let i = beforeLines.length - 1; i >= 0; i -= 1) {
    for (let j = afterLines.length - 1; j >= 0; j -= 1) {
      if (beforeLines[i] === afterLines[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  const lines = [];
  let i = 0;
  let j = 0;
  while (i < beforeLines.length && j < afterLines.length) {
    if (beforeLines[i] === afterLines[j]) {
      lines.push({ type: 'same', text: beforeLines[i] });
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      lines.push({ type: 'remove', text: beforeLines[i] });
      i += 1;
    } else {
      lines.push({ type: 'add', text: afterLines[j] });
      j += 1;
    }
  }

  while (i < beforeLines.length) {
    lines.push({ type: 'remove', text: beforeLines[i] });
    i += 1;
  }

  while (j < afterLines.length) {
    lines.push({ type: 'add', text: afterLines[j] });
    j += 1;
  }

  return lines;
}

function DiffBlock({ beforeText, afterText }) {
  const lines = useMemo(() => buildLineDiff(beforeText, afterText), [beforeText, afterText]);

  return (
    <pre className="chat-message-meta-diff">
      <code>
        {lines.map((line, index) => (
          <div
            key={`${line.type}-${index}`}
            className={`chat-message-meta-diff-line chat-message-meta-diff-line--${line.type}`}
          >
            <span className="chat-message-meta-diff-prefix">
              {line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' '}
            </span>
            <span>{line.text}</span>
          </div>
        ))}
      </code>
    </pre>
  );
}

function formatInlineArguments(argumentsValue) {
  if (argumentsValue == null) {
    return '';
  }
  if (typeof argumentsValue === 'string') {
    return argumentsValue;
  }
  const serialized = formatJson(argumentsValue).replace(/\s+/g, ' ').trim();
  return serialized.length > 100 ? `${serialized.slice(0, 99)}…` : serialized;
}

function getReasoningNotes(reasoning) {
  if (!reasoning || !Array.isArray(reasoning.notes)) {
    return [];
  }
  return reasoning.notes;
}

function getToolCalls(reasoning) {
  if (!reasoning || !Array.isArray(reasoning.tool_calls)) {
    return [];
  }
  return reasoning.tool_calls;
}

function getDisplayCharts(message) {
  if (!message || !Array.isArray(message.display_charts)) {
    return [];
  }
  return message.display_charts;
}

function isAssistantPlaceholderMessage(message) {
  if (!message || message.role !== 'assistant') {
    return false;
  }
  const id = String(message.id || '');
  return id === PENDING_ASSISTANT_ID || id.startsWith('remote-pending-');
}

function hasPendingAssistantActivity(message) {
  if (!isAssistantPlaceholderMessage(message)) {
    return false;
  }
  if (typeof message.content === 'string' && message.content.trim()) {
    return true;
  }
  if (getReasoningNotes(message.reasoning).length > 0) {
    return true;
  }
  if (getToolCalls(message.reasoning).length > 0) {
    return true;
  }
  if (getDisplayCharts(message).length > 0) {
    return true;
  }
  return false;
}

function replacePendingAssistant(messages, chatId, updater) {
  return normalizeMessageSequence(messages.map((message) => {
    const messageId = String(message.id || '');
    if (messageId !== PENDING_ASSISTANT_ID && messageId !== `remote-pending-${chatId}`) {
      return message;
    }
    return updater(message);
  }));
}

function upsertAssistantTextMessage(messages, chatId, message) {
  let replaced = false;
  const nextMessages = messages.map((current) => {
    const currentId = String(current.id || '');
    if (currentId !== PENDING_ASSISTANT_ID && currentId !== `remote-pending-${chatId}`) {
      return current;
    }
    replaced = true;
    return {
      ...message,
      reasoning: current.reasoning,
      display_charts: current.display_charts,
    };
  });

  if (!replaced && !hasMessageWithId(nextMessages, message.id)) {
    nextMessages.push(message);
  }
  return normalizeMessageSequence(nextMessages);
}

function finalizePendingAssistant(messages, chatId) {
  let changed = false;
  const finalized = messages.map((message) => {
    const messageId = String(message.id || '');
    if (messageId !== PENDING_ASSISTANT_ID && messageId !== `remote-pending-${chatId}`) {
      return message;
    }
    changed = true;
    return {
      ...message,
      id: `assistant-finalized-${chatId}-${message.request_started_at || message.created_at || Date.now()}`,
    };
  });
  return changed ? normalizeMessageSequence(finalized) : messages;
}

function hasMessageWithId(messages, messageId) {
  return messages.some((message) => message.id === messageId);
}

function appendBroadcastUserTurn(messages, userMessage, chatId, { useLocalPendingAssistant = false } = {}) {
  if (!userMessage?.id || hasMessageWithId(messages, userMessage.id) || hasEquivalentUserMessage(messages, userMessage)) {
    return messages;
  }

  const pendingAssistantId = useLocalPendingAssistant ? PENDING_ASSISTANT_ID : `remote-pending-${chatId}`;
  const nextMessages = [...messages, userMessage];
  if (!hasMessageWithId(nextMessages, pendingAssistantId)) {
    nextMessages.push({
      id: pendingAssistantId,
      role: 'assistant',
      content: '',
      model_id: userMessage.model_id || null,
      model: userMessage.model || null,
      request_started_at: userMessage.request_started_at || userMessage.created_at || Date.now(),
      created_at: userMessage.created_at || Date.now(),
      reasoning: {
        notes: [],
        tool_calls: [],
      },
      display_charts: [],
    });
  }
  return normalizeMessageSequence(nextMessages);
}

function MessageMeta({ message }) {
  if (message.id === 'intro') {
    return null;
  }

  const requestStartedAt = message.request_started_at ?? message.created_at;
  let rows;

  if (message.role === 'user') {
    rows = [
      { label: 'Message Time', value: formatTimestamp(requestStartedAt) },
    ];
  } else {
    rows = [
      { label: 'Model', value: message.model || '(unknown model)' },
      { label: 'Request Time', value: formatTimestamp(requestStartedAt) },
    ];
    if (message.id !== PENDING_ASSISTANT_ID && typeof message.created_at === 'number' && typeof requestStartedAt === 'number' && message.created_at > requestStartedAt) {
      rows.push({
        label: 'Inference Duration',
        value: formatDuration(message.created_at - requestStartedAt),
      });
    }
  }

  return (
    <div className="chat-message-meta" tabIndex={0}>
      <span className="chat-message-meta-icon" aria-label="Message metadata">i</span>
      <div className="chat-message-meta-popover">
        <div className="chat-message-meta-title">Message metadata</div>
        {rows.map((row) => (
          <div key={row.label} className="chat-message-meta-row">
            <span className="chat-message-meta-label">{row.label}</span>
            <span className="chat-message-meta-value">{row.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DisplayChartMeta({ displayChart, existingCharts }) {
  const chart = normalizeDisplayChart(displayChart.chart || {});
  const program = typeof chart.program === 'string' ? chart.program : '';
  const derivedFromId = chart.chartDerivedFrom || null;
  const baseChartCandidate = derivedFromId
    ? existingCharts.find((candidate) => candidate.id === derivedFromId) || null
    : null;
  const baseChart = baseChartCandidate ? normalizeDisplayChart(baseChartCandidate) : null;
  const previewChart = toDisplayChartMetadataPayload({
    ...chart,
    program: program ? '[PROGRAM]' : '',
  });
  const basePreviewChart = baseChart
    ? toDisplayChartMetadataPayload({
      ...baseChart,
      program: typeof baseChart.program === 'string' && baseChart.program ? '[PROGRAM]' : '',
    })
    : null;
  const previewJson = JSON.stringify(previewChart, null, 2);
  const basePreviewJson = basePreviewChart ? JSON.stringify(basePreviewChart, null, 2) : null;
  const programTitle = baseChart && typeof baseChart.program === 'string'
    ? 'Program diff'
    : 'Program';

  return (
    <div className="chat-message-meta" tabIndex={0}>
      <span className="chat-message-meta-icon" aria-label="Displayed chart parameters">i</span>
      <div className="chat-message-meta-popover chat-message-meta-popover--wide">
        <div className="chat-message-meta-title">Display Chart Parameters</div>
        {basePreviewJson ? (
          <DiffBlock beforeText={basePreviewJson} afterText={previewJson} />
        ) : (
          <pre className="chat-message-meta-json">
            <code>{toDisplayChartMetadataJson({
              ...chart,
              program: program ? '[PROGRAM]' : '',
            })}</code>
          </pre>
        )}
        {program ? (
          <>
            <div className="chat-message-meta-title chat-message-meta-title--program">{programTitle}</div>
            {baseChart && typeof baseChart.program === 'string' ? (
              <DiffBlock beforeText={baseChart.program} afterText={program} />
            ) : (
              <pre className="chat-message-meta-program">
                <code>{program}</code>
              </pre>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}

function ReasoningPanel({ reasoning, forceOpen = false, label = 'Reasoning' }) {
  const notes = getReasoningNotes(reasoning);
  const toolCalls = getToolCalls(reasoning);
  const hasContent = notes.length > 0 || toolCalls.length > 0;

  if (!forceOpen && !hasContent) {
    return null;
  }

  return (
    <div className="chat-reasoning">
      <div className="chat-reasoning-title">{label}</div>
      {!hasContent ? (
        <div className="chat-reasoning-empty">
          Waiting for Pulse Wizard to emit tool activity or intermediate notes.
        </div>
      ) : (
        <>
          {notes.length > 0 && (
            <div className="chat-reasoning-notes">
              {notes.map((note, index) => (
                <div key={`${note.round}-${index}`} className="chat-reasoning-note">
                  <div className="chat-reasoning-note-meta">assistant note after round {note.round}</div>
                  <ChatMarkdown content={note.content} />
                </div>
              ))}
            </div>
          )}
          {toolCalls.length > 0 && (
            <div className="chat-reasoning-call-list">
              {toolCalls.map((toolCall, index) => (
                <div
                  key={`${toolCall.tool_call_id || toolCall.name || 'tool'}-${index}`}
                  className="chat-reasoning-call"
                  tabIndex={0}
                >
                  <code>
                    {toolCall.name}
                    {formatInlineArguments(toolCall.arguments)
                      ? `(${formatInlineArguments(toolCall.arguments)})`
                      : '()'}
                  </code>
                  <span className="chat-reasoning-call-meta">round {toolCall.round}</span>
                  <div className="chat-reasoning-tooltip">
                    <div className="chat-reasoning-tooltip-title">Tool response</div>
                    <pre>
                      <code>{formatJson(toolCall.response)}</code>
                    </pre>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function DisplayChartsPanel({
  displayCharts,
  fallbackUpdatedAt,
  existingCharts,
  onSaveAsNew,
  onSaveToExisting,
  savingChartKey,
}) {
  const [selectedChartIds, setSelectedChartIds] = useState({});

  if (!Array.isArray(displayCharts) || displayCharts.length === 0) {
    return null;
  }

  return (
    <div className="chat-display-window">
      <div className="chat-display-window-title">Displayed Chart</div>
      <div className="chat-display-window-grid">
        {displayCharts.map((displayChart, index) => {
          const normalizedChart = normalizeDisplayChart(displayChart.chart || {}, fallbackUpdatedAt);
          const cardKey = `${displayChart.round}-${normalizedChart.name || 'chart'}-${index}`;
          const selectedExistingChartId = selectedChartIds[cardKey] || '';
          return (
            <div
              key={cardKey}
              className="chat-display-window-item"
            >
              <div className="chat-display-window-header">
                <div className="chat-display-window-meta">round {displayChart.round}</div>
                <DisplayChartMeta displayChart={displayChart} existingCharts={existingCharts} />
              </div>
              <div className="chat-display-window-actions">
                <button
                  type="button"
                  onClick={() => onSaveAsNew(normalizedChart)}
                  disabled={savingChartKey === `${cardKey}:new`}
                >
                  {savingChartKey === `${cardKey}:new` ? 'Saving...' : 'Save as New Chart'}
                </button>
                <select
                  value={selectedExistingChartId}
                  onChange={(event) => setSelectedChartIds((prev) => ({
                    ...prev,
                    [cardKey]: event.target.value,
                  }))}
                >
                  <option value="">Select existing chart</option>
                  {existingCharts.map((chart) => (
                    <option key={chart.id} value={chart.id}>
                      {chart.name || 'Untitled'}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => onSaveToExisting(selectedExistingChartId, normalizedChart)}
                  disabled={!selectedExistingChartId || savingChartKey === `${cardKey}:existing`}
                >
                  {savingChartKey === `${cardKey}:existing` ? 'Saving...' : 'Overwrite Existing'}
                </button>
              </div>
              <Chart chart={normalizedChart} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function Chat() {
  const navigate = useNavigate();
  const { chatId } = useParams();
  const {
    status: appSocketStatus,
    error: appSocketError,
    isConnected: isSocketConnected,
    connectionMeta,
    sendChatMessage,
    subscribe,
  } = useAppWebSocket();
  const [settings, setSettings] = useState(loadAiChatSettings);
  const [models, setModels] = useState([]);
  const [chats, setChats] = useState([]);
  const [currentChat, setCurrentChat] = useState(null);
  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [prompt, setPrompt] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingModels, setLoadingModels] = useState(true);
  const [loadingChats, setLoadingChats] = useState(true);
  const [loadingCurrentChat, setLoadingCurrentChat] = useState(false);
  const [availableCharts, setAvailableCharts] = useState([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [expandedReasoning, setExpandedReasoning] = useState({});
  const [savingChartKey, setSavingChartKey] = useState('');
  const activeTurnRef = useRef(null);
  const availableModels = useMemo(() => sortByName(models), [models]);
  const effectiveModelId = settings.modelId || currentChat?.model_id || '';
  const selectedModel = useMemo(
    () => availableModels.find((item) => item.id === effectiveModelId) || null,
    [availableModels, effectiveModelId],
  );
  const selectedModelIsLocalhost = !!selectedModel?.settings?.is_localhost;

  async function reloadModels() {
    try {
      setLoadingModels(true);
      const data = await api.listLlmModels();
      setModels(Array.isArray(data) ? data : []);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load saved models');
    } finally {
      setLoadingModels(false);
    }
  }

  async function reloadChats() {
    try {
      setLoadingChats(true);
      const data = await api.listChats();
      setChats(Array.isArray(data) ? data : []);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load chat history');
    } finally {
      setLoadingChats(false);
    }
  }

  async function reloadAvailableCharts() {
    try {
      const data = await api.listCharts();
      setAvailableCharts(Array.isArray(data) ? data.map(normalizeChart) : []);
    } catch {
      // Keep chat usable even if chart list refresh fails.
    }
  }

  async function reloadSpecificChat(targetChatId) {
    if (!targetChatId) {
      return;
    }
    const data = await api.getChat(targetChatId);
    applyLoadedChat(data);
  }

  useEffect(() => {
    reloadModels();
    reloadChats();
    reloadAvailableCharts();
  }, []);

  useEffect(() => {
    if (!notice) {
      return undefined;
    }
    const timeoutId = window.setTimeout(() => setNotice(''), 3000);
    return () => window.clearTimeout(timeoutId);
  }, [notice]);

  useEffect(() => {
    saveAiChatSettings(settings);
  }, [settings]);

  useEffect(() => {
    return subscribe(async (message) => {
      const ownConnectionId = connectionMeta?.connection_id || '';
      const isOwnEvent = !!(message.source_connection_id && message.source_connection_id === ownConnectionId);
      const activeChatId = currentChat?.id || activeTurnRef.current?.chatId || null;

      if (message.type === 'chat_id_assigned') {
        if (activeTurnRef.current && !activeTurnRef.current.chatId && message.chat_id) {
          activeTurnRef.current.chatId = message.chat_id;
          setCurrentChat((prev) => prev && prev.id === message.chat_id ? prev : {
            id: message.chat_id,
            model_id: effectiveModelId,
            model: selectedModel?.model || null,
            title: activeTurnRef.current.pendingTitle || 'New chat',
            created_at: Date.now(),
            updated_at: Date.now(),
          });
          navigate(`/chat/${message.chat_id}`, { replace: true });
          await reloadChats();
        }
        return;
      }

      if (message.type === 'chat_message') {
        const incomingChatId = message.chat_id;
        const savedMessage = message.message;
        if (!incomingChatId || !savedMessage) {
          return;
        }

        if (savedMessage.role === 'user') {
          if (incomingChatId === activeChatId) {
            setMessages((prev) => appendBroadcastUserTurn(
              prev,
              savedMessage,
              incomingChatId,
              { useLocalPendingAssistant: isOwnEvent },
            ));
          }
        } else if (savedMessage.role === 'assistant' && incomingChatId === activeChatId) {
          setMessages((prev) => upsertAssistantTextMessage(prev, incomingChatId, savedMessage));
        }
        await reloadChats();
        return;
      }

      if (message.type === 'chat_assistant_note') {
        if (!message.chat_id || message.chat_id !== activeChatId) {
          return;
        }
        setMessages((prev) => replacePendingAssistant(prev, message.chat_id, (assistantMessage) => ({
          ...assistantMessage,
          reasoning: {
            ...(assistantMessage.reasoning || { notes: [], tool_calls: [] }),
            notes: [
              ...getReasoningNotes(assistantMessage.reasoning),
              message.note,
            ],
            tool_calls: getToolCalls(assistantMessage.reasoning),
          },
        })));
        return;
      }

      if (message.type === 'chat_tool') {
        if (!message.chat_id || message.chat_id !== activeChatId) {
          return;
        }
        setMessages((prev) => replacePendingAssistant(prev, message.chat_id, (assistantMessage) => ({
          ...assistantMessage,
          reasoning: {
            notes: getReasoningNotes(assistantMessage.reasoning),
            tool_calls: [
              ...getToolCalls(assistantMessage.reasoning),
              message.tool_call,
            ],
          },
        })));
        return;
      }

      if (message.type === 'chat_display_chart') {
        if (!message.chat_id || message.chat_id !== activeChatId) {
          return;
        }
        setMessages((prev) => replacePendingAssistant(prev, message.chat_id, (assistantMessage) => ({
          ...assistantMessage,
          display_charts: [
            ...getDisplayCharts(assistantMessage),
            message.display_chart,
          ],
        })));
        return;
      }

      if (message.type === 'chat_done') {
        if (!message.chat_id) {
          return;
        }
        if (message.chat_id === activeChatId) {
          setMessages((prev) => finalizePendingAssistant(prev, message.chat_id));
        }
        if (activeTurnRef.current?.chatId === message.chat_id) {
          activeTurnRef.current = null;
          setSending(false);
          setError('');
        }
        await reloadChats();
        return;
      }

      if (message.type === 'chat_error') {
        const activeTurn = activeTurnRef.current;
        activeTurnRef.current = null;
        setSending(false);
        if (activeTurn?.chatId) {
          try {
            await reloadSpecificChat(activeTurn.chatId);
          } catch {
            setMessages(activeTurn.previousMessages);
          }
        } else if (activeTurn?.previousMessages) {
          setMessages(activeTurn.previousMessages);
        }
        setError(message.error || 'Chat websocket failed');
      }
    });
  }, [subscribe, connectionMeta?.connection_id, currentChat?.id, effectiveModelId, navigate, selectedModel?.model]);

  useEffect(() => {
    if (availableModels.length === 0) {
      if (!settings.modelId) {
        return;
      }
      setSettings((prev) => ({
        ...prev,
        modelId: '',
      }));
      return;
    }
    if (!availableModels.some((item) => item.id === settings.modelId)) {
      if (settings.modelId === availableModels[0].id) {
        return;
      }
      setSettings((prev) => ({
        ...prev,
        modelId: availableModels[0].id,
      }));
    }
  }, [availableModels, settings.modelId]);

  useEffect(() => {
    let cancelled = false;

    async function loadChat() {
      if (!chatId) {
        setCurrentChat((prev) => (prev === null ? prev : null));
        setMessages((prev) => (prev === INITIAL_MESSAGES ? prev : INITIAL_MESSAGES));
        setExpandedReasoning((prev) => (Object.keys(prev).length === 0 ? prev : {}));
        setError((prev) => (prev ? '' : prev));
        return;
      }
      if (sending && currentChat?.id === chatId) {
        return;
      }
      if (currentChat?.id === chatId) {
        return;
      }

      try {
        setLoadingCurrentChat(true);
        const data = await api.getChat(chatId);
        if (cancelled) {
          return;
        }
        applyLoadedChat(data);
        setError('');
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Failed to load chat');
        }
      } finally {
        if (!cancelled) {
          setLoadingCurrentChat(false);
        }
      }
    }

    loadChat();
    return () => {
      cancelled = true;
    };
  }, [chatId, currentChat?.id, sending]);

  function updateSetting(field, value) {
    setSettings((prev) => ({
      ...prev,
      [field]: value,
    }));
  }

  function startNewChat() {
    setPrompt('');
    setError('');
    setSending(false);
    activeTurnRef.current = null;
    setCurrentChat(null);
    setMessages(INITIAL_MESSAGES);
    setExpandedReasoning({});
    navigate('/chat');
  }

  function applyLoadedChat(chat) {
    setCurrentChat(chat);
    setMessages(normalizeMessages(chat?.messages));
    setExpandedReasoning({});
  }

  function getChatSocketStatusLabel() {
    if (appSocketStatus === 'connected') {
      return selectedModelIsLocalhost
        ? 'Connected. Chat and localhost model routing run over this websocket session.'
        : 'Connected. Chat runs over a live websocket stream.';
    }
    if (appSocketStatus === 'connecting') {
      return 'Connecting. Waiting for the websocket.';
    }
    if (appSocketStatus === 'error') {
      return appSocketError || 'Disconnected. The websocket hit an error.';
    }
    return appSocketError || 'Disconnected. Chat cannot send until the websocket reconnects.';
  }

  function toggleReasoning(messageId) {
    setExpandedReasoning((prev) => ({
      ...prev,
      [messageId]: !prev[messageId],
    }));
  }

  async function handleSaveDisplayedChartAsNew(chart, saveKey) {
    try {
      setSavingChartKey(saveKey);
      setError('');
      await api.createChart(toChartBody(chart));
      await reloadAvailableCharts();
      setNotice(`Saved "${chart.name || 'Untitled'}" as a new chart`);
    } catch (err) {
      setError(err.message || 'Failed to save chart');
    } finally {
      setSavingChartKey('');
    }
  }

  async function handleSaveDisplayedChartToExisting(chartId, chart, saveKey) {
    if (!chartId) {
      return;
    }
    if (!window.confirm(`Overwrite the existing chart with "${chart.name || 'Untitled'}"?`)) {
      return;
    }
    try {
      setSavingChartKey(saveKey);
      setError('');
      await api.updateChart(chartId, toChartBody(chart));
      await reloadAvailableCharts();
      setNotice(`Updated chart from "${chart.name || 'Untitled'}"`);
    } catch (err) {
      setError(err.message || 'Failed to update chart');
    } finally {
      setSavingChartKey('');
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt) {
      setError('Prompt is required');
      return;
    }
    if (!effectiveModelId) {
      setError('Pick a saved model');
      return;
    }
    if (!isSocketConnected) {
      setError('Chat websocket is not connected');
      return;
    }
    if (!sendChatMessage({
      chatId: currentChat?.id || null,
      modelId: effectiveModelId,
      content: trimmedPrompt,
    })) {
      setError('Chat websocket is not connected');
      return;
    }

    const previousMessages = messages;
    setPrompt('');
    setSending(true);
    setError('');
    activeTurnRef.current = {
      previousMessages,
      chatId: currentChat?.id || null,
      pendingTitle: trimmedPrompt,
    };
  }

  function handlePromptKeyDown(event) {
    if (event.key !== 'Enter' || event.shiftKey) {
      return;
    }
    event.preventDefault();
    if (sending || !isSocketConnected) {
      return;
    }
    event.currentTarget.form?.requestSubmit();
  }

  function handleChatSelection(event) {
    const value = event.target.value;
    if (value === NEW_CHAT_VALUE) {
      startNewChat();
      return;
    }
    navigate(`/chat/${value}`);
  }

  const selectedChatValue = chatId || NEW_CHAT_VALUE;
  const selectedModelControl = (
    <label className="chat-model-inline">
      <span>Model</span>
      <select
        value={effectiveModelId}
        onChange={(event) => updateSetting('modelId', event.target.value)}
        disabled={availableModels.length === 0}
      >
        {availableModels.length === 0 && (
          <option value="">No saved models</option>
        )}
        {availableModels.map((item) => (
          <option key={item.id} value={item.id}>
            {item.model || '(missing model name)'} - {item.settings?.base_url || 'Untitled model'} {item.settings?.is_localhost ? '(localhost)' : '(remote)'}
          </option>
        ))}
      </select>
    </label>
  );
  const transcriptContent = useMemo(() => {
    if (loadingCurrentChat) {
      return <div className="chat-loading">Loading chat...</div>;
    }

    return messages
      .filter((message) => !isAssistantPlaceholderMessage(message) || hasPendingAssistantActivity(message))
      .map((message, index) => {
        const messageId = message.id || `${message.role}-${index}`;
        const hasReasoning = getReasoningNotes(message.reasoning).length > 0 || getToolCalls(message.reasoning).length > 0;
        const displayCharts = getDisplayCharts(message);
        const isPlaceholderMessage = isAssistantPlaceholderMessage(message);
        const showReasoningButton = !isPlaceholderMessage && hasReasoning;
        const isReasoningOpen = isPlaceholderMessage ? true : !!expandedReasoning[messageId];

        return (
          <div
            key={messageId}
            className={`chat-message chat-message--${message.role}${isPlaceholderMessage ? ' chat-message--pending' : ''}`}
          >
            <div className="chat-message-header">
              <div className="chat-message-header-left">
                <div className="chat-message-role">{message.role}</div>
                <MessageMeta message={message} />
              </div>
              {showReasoningButton && (
                <button
                  type="button"
                  className="chat-reasoning-toggle"
                  onClick={() => toggleReasoning(messageId)}
                >
                  {isReasoningOpen ? 'Hide reasoning' : 'Show reasoning'}
                </button>
              )}
            </div>
            {isPlaceholderMessage ? (
              <ReasoningPanel reasoning={message.reasoning} forceOpen={true} label="Thinking..." />
            ) : (
              isReasoningOpen && (
                <ReasoningPanel reasoning={message.reasoning} label="Tool activity" />
              )
            )}
            <DisplayChartsPanel
              displayCharts={displayCharts}
              fallbackUpdatedAt={message.created_at || message.request_started_at || Date.now()}
              existingCharts={availableCharts}
              savingChartKey={savingChartKey}
              onSaveAsNew={(chart) => handleSaveDisplayedChartAsNew(chart, `${messageId}:${chart.name || 'chart'}:new`)}
              onSaveToExisting={(chartIdValue, chart) => handleSaveDisplayedChartToExisting(chartIdValue, chart, `${messageId}:${chart.name || 'chart'}:existing`)}
            />
            {message.content ? (
              <ChatMarkdown content={message.content} />
            ) : (
              isPlaceholderMessage && (
                <div className="chat-reasoning-empty">Waiting for the final assistant answer...</div>
              )
            )}
          </div>
        );
      });
  }, [availableCharts, expandedReasoning, loadingCurrentChat, messages, savingChartKey]);

  return (
    <div>
      <h2>Chat</h2>
      <p>Read-only assistant for chart, dashboard, metric, and PulseLang analysis. Pick a saved model for any turn, or reopen an older conversation below.</p>

      {error && <div className="error">{error}</div>}
      {notice && <div className="success">{notice}</div>}

      <div className="card">
        <div className="chat-toolbar">
          <h3>Saved Chats</h3>
          <div className="button-group">
            <button type="button" onClick={reloadChats} disabled={loadingChats}>
              {loadingChats ? 'Loading...' : 'Reload Chats'}
            </button>
            <button type="button" onClick={startNewChat}>New Chat</button>
          </div>
        </div>
        <label className="chat-history-select chat-history-select--top">
          Saved Chats
          <select
            value={selectedChatValue}
            onChange={handleChatSelection}
            disabled={loadingChats}
          >
            <option value={NEW_CHAT_VALUE}>New chat</option>
            {chats.map((chat) => (
              <option key={chat.id} value={chat.id}>
                {formatChatTitle(chat)} {chat.model ? `· ${chat.model}` : ''}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="card">
        <div className="chat-toolbar">
          <h3>Conversation</h3>
        </div>

        <p>Existing chats are not pinned to one model. The model selected next to Send is used for the next turn.</p>

        <div className="chat-ws-status">
          <span
            className={`chat-ws-status-dot ${appSocketStatus === 'connected' ? 'chat-ws-status-dot--connected' : 'chat-ws-status-dot--disconnected'}`}
            aria-hidden="true"
          />
          <span>{getChatSocketStatusLabel()}</span>
        </div>

        <div className="chat-transcript">
          {transcriptContent}
        </div>

        <form onSubmit={handleSubmit} className="chat-form">
          <label>
            Prompt
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={handlePromptKeyDown}
              placeholder="Ask about a saved chart or dashboard by name, how it is built, suspicious patterns, metric shape, PulseLang issues, and so on."
              rows={6}
              disabled={sending || loadingCurrentChat}
            />
          </label>
          <div className="chat-form-actions">
            <div className="button-group">
              <button type="submit" disabled={sending || loadingCurrentChat || !isSocketConnected}>
                {sending ? 'Thinking...' : 'Send'}
              </button>
            </div>
            {selectedModelControl}
          </div>
        </form>
      </div>
    </div>
  );
}
