import { useUserSettings } from '../contexts/UserSettingsContext';

export default function Settings() {
  const { hideSensitiveData, setHideSensitiveData } = useUserSettings();

  return (
    <div className="card">
      <h2>Settings</h2>

      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={hideSensitiveData}
          onChange={(e) => setHideSensitiveData(e.target.checked)}
        />
        Hide sensitive data in charts
      </label>
      <p className="layout-empty-hint">
        When enabled, numeric chart values are replaced with the text "Sensitive data".
      </p>
    </div>
  );
}
