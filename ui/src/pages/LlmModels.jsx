import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';

function emptyHeader() {
  return { name: '', value: '' };
}

function emptyForm() {
  return {
    id: null,
    modelName: '',
    baseUrl: '',
    headers: [emptyHeader()],
    isLocalhost: false,
  };
}

function normalizeHeaders(headers) {
  const filtered = headers.filter((header) => header.name.trim() || header.value.trim());
  return filtered.length > 0 ? filtered : [emptyHeader()];
}

function sortModels(models) {
  return [...models].sort((a, b) => {
    const left = a.model || '';
    const right = b.model || '';
    return left.localeCompare(right);
  });
}

export default function LlmModels() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [form, setForm] = useState(emptyForm());

  const sortedModels = useMemo(() => sortModels(models), [models]);
  const isEditing = !!form.id;

  useEffect(() => {
    loadModels();
  }, []);

  useEffect(() => {
    if (!notice) {
      return undefined;
    }
    const timeoutId = window.setTimeout(() => setNotice(''), 3000);
    return () => window.clearTimeout(timeoutId);
  }, [notice]);

  async function loadModels() {
    try {
      setLoading(true);
      const data = await api.listLlmModels();
      setModels(Array.isArray(data) ? data : []);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load models');
    } finally {
      setLoading(false);
    }
  }

  function resetForm() {
    setForm(emptyForm());
  }

  function startEdit(model) {
    setForm({
      id: model.id,
      modelName: model.model || '',
      baseUrl: model.settings.base_url || '',
      headers: normalizeHeaders(
        Array.isArray(model.settings.headers)
          ? model.settings.headers.map((header) => ({
              name: header.name || '',
              value: header.value || '',
            }))
          : []
      ),
      isLocalhost: !!model.settings.is_localhost,
    });
    setError('');
  }

  function updateForm(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function updateHeader(index, field, value) {
    setForm((prev) => {
      const headers = [...prev.headers];
      headers[index] = {
        ...headers[index],
        [field]: value,
      };
      return { ...prev, headers };
    });
  }

  function addHeader() {
    setForm((prev) => ({
      ...prev,
      headers: [...prev.headers, emptyHeader()],
    }));
  }

  function removeHeader(index) {
    setForm((prev) => {
      const next = prev.headers.filter((_, idx) => idx !== index);
      return {
        ...prev,
        headers: next.length > 0 ? next : [emptyHeader()],
      };
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');

    const payload = {
      model: form.modelName.trim(),
      settings: {
        base_url: form.baseUrl.trim(),
        headers: form.headers
          .filter((header) => header.name.trim() || header.value.trim())
          .map((header) => ({
            name: header.name.trim(),
            value: header.value.trim(),
          })),
        is_localhost: !!form.isLocalhost,
      },
    };

    if (!payload.model) {
      setError('Model name is required');
      return;
    }

    if (!payload.settings.base_url) {
      setError('Base URL is required');
      return;
    }

    if (!payload.settings.is_localhost) {
      const confirmed = confirm(
        'This model is not localhost. Its headers will be stored without envelope encryption, which is not safe yet. Save anyway?'
      );
      if (!confirmed) {
        return;
      }
    }

    try {
      setSaving(true);
      if (form.id) {
        await api.updateLlmModel(form.id, payload);
        setNotice('Model updated');
      } else {
        await api.createLlmModel(payload);
        setNotice('Model created');
      }
      await loadModels();
      resetForm();
    } catch (err) {
      setError(err.message || 'Failed to save model');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(modelId) {
    if (!confirm('Delete this model?')) {
      return;
    }

    try {
      await api.deleteLlmModel(modelId);
      setNotice('Model deleted');
      if (form.id === modelId) {
        resetForm();
      }
      await loadModels();
    } catch (err) {
      setError(err.message || 'Failed to delete model');
    }
  }

  if (loading) {
    return <div className="loading">Loading models...</div>;
  }

  return (
    <div>
      <h2>LLM Models</h2>
      <p>Manage stored server-side LLM connection models for future chat execution.</p>

      {error && <div className="error">{error}</div>}
      {notice && <div className="success">{notice}</div>}

      <div className="card">
        <div className="chat-toolbar">
          <h3>{isEditing ? 'Edit Model' : 'Create Model'}</h3>
          {isEditing && (
            <button type="button" onClick={resetForm}>New Model</button>
          )}
        </div>

        {!form.isLocalhost && (
          <div className="error">
            Remote model headers are currently stored without envelope encryption. This is not safe for sensitive credentials.
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <label>
            Model Name
            <input
              type="text"
              value={form.modelName}
              onChange={(event) => updateForm('modelName', event.target.value)}
              placeholder="gpt-4.1-mini"
              required
            />
          </label>

          <label>
            Base URL
            <input
              type="text"
              value={form.baseUrl}
              onChange={(event) => updateForm('baseUrl', event.target.value)}
              placeholder="https://api.openai.com/v1"
              required
            />
          </label>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={form.isLocalhost}
              onChange={(event) => updateForm('isLocalhost', event.target.checked)}
            />
            Localhost model
          </label>

          <div className="impulses-section">
            <h4>Headers</h4>
            {form.headers.map((header, index) => (
              <div key={index} className="impulse-row">
                <input
                  type="text"
                  value={header.name}
                  onChange={(event) => updateHeader(index, 'name', event.target.value)}
                  placeholder="Authorization"
                />
                <input
                  type="text"
                  value={header.value}
                  onChange={(event) => updateHeader(index, 'value', event.target.value)}
                  placeholder="Bearer ..."
                />
                <button type="button" onClick={() => removeHeader(index)}>Remove</button>
              </div>
            ))}
            <button type="button" onClick={addHeader}>Add Header</button>
          </div>

          <div className="button-group">
            <button type="submit" disabled={saving}>
              {saving ? 'Saving...' : isEditing ? 'Update Model' : 'Create Model'}
            </button>
            {isEditing && (
              <button type="button" onClick={resetForm}>Cancel</button>
            )}
          </div>
        </form>
      </div>

      <h3>Your Models ({sortedModels.length})</h3>
      {sortedModels.length === 0 ? (
        <p>No models yet. Create one above.</p>
      ) : (
        <div>
          {sortedModels.map((model) => (
            <div key={model.id} className="token-item">
              <div>
                <strong>{model.model || '(missing model name)'}</strong>
                <br />
                <small>
                  {model.settings.base_url} |
                  {' '}{model.settings.is_localhost ? 'localhost' : 'remote'} |
                  {' '}headers: {Array.isArray(model.settings.headers) ? model.settings.headers.length : 0} |
                  {' '}updated: {new Date(model.updated_at * 1000).toLocaleString()}
                </small>
              </div>
              <div className="button-group" style={{ margin: 0 }}>
                <button onClick={() => startEdit(model)}>Edit</button>
                <button onClick={() => handleDelete(model.id)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
