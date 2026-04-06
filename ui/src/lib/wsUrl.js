export function getApiBase() {
  return import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL : '/impulses/api';
}

export function buildAppWebSocketUrl(pathname) {
  const apiBase = getApiBase().replace(/\/$/, '');
  const normalizedPathname = pathname.startsWith('/') ? pathname : `/${pathname}`;

  if (apiBase.startsWith('http://') || apiBase.startsWith('https://')) {
    const url = new URL(apiBase);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = `${url.pathname.replace(/\/$/, '')}${normalizedPathname}`;
    url.search = '';
    url.hash = '';
    return url.toString();
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${apiBase}${normalizedPathname}`;
}
