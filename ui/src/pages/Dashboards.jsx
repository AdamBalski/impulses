import { useState, useEffect, useRef } from 'react';
import { compute, COMMON_LIBRARY } from '@impulses/sdk-typescript';
import { getImpulsesClient } from '../lib/sdkClient';
import { useParams, useNavigate } from 'react-router-dom';
import DashboardLayout from '../components/DashboardLayout';
import DashboardPicker from '../components/DashboardPicker';
import DashboardEditor from '../components/DashboardEditor';
import DashboardZoomControls from '../components/DashboardZoomControls';
import { loadChartsFromStorage } from '../lib/chartStorage';
import {
  loadDashboardsFromStorage,
  saveDashboard,
  deleteDashboard,
  copyDashboard,
  createDashboard,
} from '../lib/dashboardStorage';

export default function Dashboards() {
  const { dashboardId } = useParams();
  const navigate = useNavigate();

  const [chartsMap, setChartsMap] = useState({});
  const [dashboardsMap, setDashboardsMap] = useState({});
  const [isEditing, setIsEditing] = useState(false);
  const [globalZoomCommand, setGlobalZoomCommand] = useState(null);
  const [dashboardSeriesData, setDashboardSeriesData] = useState({});
  const [dashboardDataLoading, setDashboardDataLoading] = useState(false);
  const [dashboardDataError, setDashboardDataError] = useState('');
  const lastComputedProgramRef = useRef(null);

  useEffect(() => {
    setChartsMap(loadChartsFromStorage());
    setDashboardsMap(loadDashboardsFromStorage());
  }, []);

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

  function handleNewDashboard() {
    const newDashboard = createDashboard();
    saveDashboard(newDashboard);
    setDashboardsMap(loadDashboardsFromStorage());
    navigate(`/dashboards/${newDashboard.id}`);
    setIsEditing(true);
  }

  function handleToggleEdit() {
    setIsEditing(!isEditing);
  }

  function handleSave(updatedDashboard) {
    saveDashboard(updatedDashboard);
    setDashboardsMap(loadDashboardsFromStorage());
    setIsEditing(false);
  }

  function handleDelete(id) {
    deleteDashboard(id);
    setDashboardsMap(loadDashboardsFromStorage());
    setIsEditing(false);
    navigate('/dashboards');
  }

  function handleCopy(id) {
    const copied = copyDashboard(id);
    if (copied) {
      setDashboardsMap(loadDashboardsFromStorage());
      navigate(`/dashboards/${copied.id}`);
      setIsEditing(true);
    }
  }

  function handleCancelEdit() {
    setIsEditing(false);
  }

  const hasDashboards = Object.keys(dashboardsMap).length > 0;

  return (
    <div>
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
