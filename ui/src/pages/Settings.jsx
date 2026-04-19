import { NavLink, Outlet } from 'react-router-dom';

const SETTINGS_TABS = [
  { to: '/settings', label: 'General', end: true },
  { to: '/settings/tokens', label: 'Tokens' },
  { to: '/settings/gcal-integration', label: 'GCal integration' },
  { to: '/settings/models', label: 'Models' },
  { to: '/settings/storage-sync', label: 'Storage sync' },
];

export default function Settings() {
  return (
    <div>
      <h2>Settings</h2>
      <div className="settings-subtabs">
        {SETTINGS_TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) => `settings-subtab${isActive ? ' settings-subtab--active' : ''}`}
          >
            {tab.label}
          </NavLink>
        ))}
      </div>
      <Outlet />
    </div>
  );
}
