import { createContext, useContext, useCallback, useMemo, useState } from 'react';

const STORAGE_KEY = 'hide_sensitive_data_toggle';

const UserSettingsContext = createContext({
  hideSensitiveData: false,
  setHideSensitiveData: () => {},
});

function readInitialValue() {
  if (typeof window === 'undefined') {
    return false;
  }
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

export function UserSettingsProvider({ children }) {
  const [hideSensitiveData, setHideSensitiveDataState] = useState(readInitialValue);

  const setHideSensitiveData = useCallback((value) => {
    setHideSensitiveDataState(value);
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.setItem(STORAGE_KEY, String(!!value));
      } catch {
        // ignore storage errors
      }
    }
  }, []);

  const value = useMemo(
    () => ({ hideSensitiveData, setHideSensitiveData }),
    [hideSensitiveData, setHideSensitiveData],
  );

  return (
    <UserSettingsContext.Provider value={value}>
      {children}
    </UserSettingsContext.Provider>
  );
}

export function useUserSettings() {
  return useContext(UserSettingsContext);
}
