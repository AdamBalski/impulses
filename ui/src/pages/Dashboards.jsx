import { useState, useEffect, useRef } from 'react';
import { compute, COMMON_LIBRARY } from '@impulses/sdk-typescript';
import { getImpulsesClient } from '../lib/sdkClient';
import { useParams, useNavigate } from 'react-router-dom';
import DashboardLayout from '../components/DashboardLayout';
import DashboardPicker from '../components/DashboardPicker';
import DashboardEditor from '../components/DashboardEditor';
import DashboardZoomControls from '../components/DashboardZoomControls';
import { normalizeChart, normalizeDashboard, toDashboardBody } from '../lib/visualizationModel';
import { api } from '../api';

export default function Dashboards() {
  const { dashboardId } = useParams();
  const navigate = useNavigate();

  const [chartsMap, setChartsMap] = useState({});
  const [dashboardsMap, setDashboardsMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [globalZoomCommand, setGlobalZoomCommand] = useState(null);
  const [dashboardSeriesData, setDashboardSeriesData] = useState({});
  const [dashboardDataLoading, setDashboardDataLoading] = useState(false);
  const [dashboardDataError, setDashboardDataError] = useState('');
  const [error, setError] = useState('');
  const lastComputedProgramRef = useRef(null);

  useEffect(() => {
    loadVisualizations();
  }, []);

  async function loadVisualizations() {
    try {
      setLoading(true);
      const [charts, dashboards] = await Promise.all([
        api.listCharts(),
        api.listDashboards(),
      ]);

      const nextChartsMap = {};
      for (const chart of charts || []) {
        const normalized = normalizeChart(chart);
        nextChartsMap[normalized.id] = normalized;
      }

      const nextDashboardsMap = {};
      for (const dashboard of dashboards || []) {
        const normalized = normalizeDashboard(dashboard);
        nextDashboardsMap[normalized.id] = normalized;
      }

      setChartsMap(nextChartsMap);
      setDashboardsMap(nextDashboardsMap);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load dashboards');
    } finally {
      setLoading(false);
    }
  }

  const currentDashboard = dashboardId ? dashboardsMap[dashboardId] : null;

  useEffect(() => {
    if (!currentDashboard?.program?.trim()) {
      setDashboardSeriesData({});
      setDashboardDataError('');
      lastComputedProgramRef.current = null;
      return;
    }

    const programKey = `${currentDashboard.id}:${currentDashboard.program}`;
    if (lastComputedProgramRef.current === programKey) {
      return;
    }

    async function computeDashboardProgram() {
      setDashboardDataLoading(true);
      setDashboardDataError('');
      try {
        const client = getImpulsesClient();
        const resultMap = await compute(client, COMMON_LIBRARY, currentDashboard.program);
        const seriesData = {};
        for (const [name, series] of resultMap.entries()) {
          if (series && typeof series.toDTO === 'function') {
            seriesData[name] = series.toDTO();
          }
        }
        setDashboardSeriesData(seriesData);
        lastComputedProgramRef.current = programKey;
      } catch (err) {
        console.error('Failed to compute dashboard program', err);
        setDashboardDataError(err?.message || 'Failed to compute dashboard program');
        setDashboardSeriesData({});
      } finally {
        setDashboardDataLoading(false);
      }
    }

    computeDashboardProgram();
  }, [currentDashboard?.id, currentDashboard?.program]);

  function handleGlobalPreset(preset) {
    setGlobalZoomCommand({
      id: `${Date.now()}_${Math.random().toString(36).slice(2)}`,
      type: 'preset',
      durationMs: preset.durationMs,
    });
  }

  function handleGlobalReset() {
    setGlobalZoomCommand({
      id: `${Date.now()}_${Math.random().toString(36).slice(2)}`,
      type: 'reset',
    });
  }

  function handleGlobalCustomWindow(window) {
    setGlobalZoomCommand({
      id: `${Date.now()}_${Math.random().toString(36).slice(2)}`,
      type: 'custom',
      start: window.start,
      end: window.end,
    });
  }

  async function handleNewDashboard() {
    try {
      const newDashboard = await api.createDashboard({
        name: 'Unnamed',
        description: '',
        program: '',
        default_zoom_window: null,
        override_chart_zoom: false,
        layout: [],
      });
      await loadVisualizations();
      navigate(`/dashboards/${newDashboard.id}`);
      setIsEditing(true);
    } catch (err) {
      setError(err.message || 'Failed to create dashboard');
    }
  }

  function handleToggleEdit() {
    setIsEditing(!isEditing);
  }

  async function handleSave(updatedDashboard) {
    try {
      await api.updateDashboard(updatedDashboard.id, toDashboardBody(updatedDashboard));
      await loadVisualizations();
      setIsEditing(false);
    } catch (err) {
      setError(err.message || 'Failed to save dashboard');
    }
  }

  async function handleDelete(id) {
    try {
      await api.deleteDashboard(id);
      await loadVisualizations();
      setIsEditing(false);
      navigate('/dashboards');
    } catch (err) {
      setError(err.message || 'Failed to delete dashboard');
    }
  }

  async function handleCopy(id) {
    const original = dashboardsMap[id];
    if (!original) {
      return;
    }
    try {
      const copied = await api.createDashboard({
        ...toDashboardBody(original),
        name: `${original.name} (copy)`,
      });
      await loadVisualizations();
      navigate(`/dashboards/${copied.id}`);
      setIsEditing(true);
    } catch (err) {
      setError(err.message || 'Failed to copy dashboard');
    }
  }

  function handleCancelEdit() {
    setIsEditing(false);
  }

  const hasDashboards = Object.keys(dashboardsMap).length > 0;

  if (loading) {
    return <div className="loading">Loading dashboards...</div>;
  }

  return (
    <div>
      {error && <div className="error">{error}</div>}

      <DashboardPicker
        dashboards={dashboardsMap}
        onNew={handleNewDashboard}
        onEdit={handleToggleEdit}
        isEditing={isEditing}
      />

      {dashboardId && (
        <DashboardZoomControls onPreset={handleGlobalPreset} onReset={handleGlobalReset} onCustomWindow={handleGlobalCustomWindow} />
      )}

      {isEditing && currentDashboard && (
        <DashboardEditor
          dashboard={currentDashboard}
          chartsMap={chartsMap}
          onSave={handleSave}
          onDelete={handleDelete}
          onCancel={handleCancelEdit}
          onCopy={handleCopy}
        />
      )}

      {!dashboardId && (
        <div className="card">
          <p>
            {hasDashboards
              ? 'Select a dashboard from the tabs above to view it.'
              : 'No dashboards yet. Click "+ New" to create your first dashboard.'}
          </p>
        </div>
      )}

      {dashboardId && currentDashboard && !isEditing && (
        <>
          {(currentDashboard.layout?.length ?? 0) === 0 ? (
            <div className="card">
              <p>No charts configured for this dashboard yet.</p>
              <p>Please click "Edit" above and add charts to the layout.</p>
            </div>
          ) : (
            <div className="dashboard-viewport-breakout">
              {dashboardDataLoading && (
                <div className="card">
                  <p>Loading dashboard data...</p>
                </div>
              )}
              {dashboardDataError && (
                <div className="error">
                  <p>Dashboard program error: {dashboardDataError}</p>
                </div>
              )}
              <DashboardLayout
                layout={currentDashboard.layout || []}
                chartsMap={chartsMap}
                globalZoomCommand={globalZoomCommand}
                dashboardSeriesData={currentDashboard?.program?.trim() ? dashboardSeriesData : null}
                dashboardDefaultZoomWindow={currentDashboard?.defaultZoomWindow || null}
                dashboardOverrideChartZoom={!!currentDashboard?.overrideChartZoom}
              />
            </div>
          )}
        </>
      )}

      {dashboardId && !currentDashboard && (
        <div className="card">
          <p>Dashboard not found. It may have been deleted.</p>
        </div>
      )}
    </div>
  );
}
