// A sandboxed iframe without allow-same-origin reports the opaque origin "null".
export const opaqueOrigin = typeof window !== 'undefined' && (() => { try { return window.origin === 'null' || window.origin === null; } catch { return false; } })();
let csrf = '';
// Opt-in cookie-less transport. Some embedded hosts (sandboxed cross-site
// preview iframes) refuse to store cookies at all, so the HttpOnly session
// cookie never arrives and every mutation fails CSRF. When the server enables
// it, we hold the opaque session token in memory and echo it back per request.
let sessionToken = '';
export function setCsrf(token: string) { csrf = token; }
export function setSessionToken(token?: string) { sessionToken = token || ''; }
function authHeaders(headers: Headers) {
  if (sessionToken) headers.set('X-Session-Token', sessionToken);
  return headers;
}
async function refreshCsrf(): Promise<boolean> {
  try {
    const r = await fetch('/api/auth/session', { credentials: 'same-origin', cache: 'no-store' });
    if (!r.ok) return false;
    const s = await r.json();
    if (s.session_token !== undefined) setSessionToken(s.session_token);
    if (s.csrf_token) { csrf = s.csrf_token; return true; }
  } catch { /* ignore */ }
  return false;
}
export class ApiError extends Error { constructor(public code: string, message: string, public status: number) { super(message); this.name = 'ApiError'; } }
export async function api<T = any>(path: string, options: RequestInit = {}, retried = false): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  authHeaders(headers);
  if (!['GET', 'HEAD'].includes(options.method || 'GET')) headers.set('X-CSRF-Token', csrf);
  const response = await fetch(path, { ...options, headers, credentials: 'same-origin', cache: 'no-store' });
  if (!response.ok) {
    let message = 'The request could not be completed. Please try again.'; let code = 'request_failed';
    try { const data = await response.json(); message = data.error?.message || message; code = data.error?.code || code; } catch { /* ignore */ }
    // In no-login mode the session can be re-provisioned transparently; refresh
    // the CSRF token and retry once instead of surfacing a confusing error.
    if (response.status === 403 && code === 'csrf_failed' && !retried && await refreshCsrf()) {
      return api<T>(path, options, true);
    }
    throw new ApiError(code, message, response.status);
  }
  return response.json();
}
export const post = <T = any>(path: string, body?: unknown) => api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
export const patch = <T = any>(path: string, body: unknown) => api<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
export const del = <T = any>(path: string) => api<T>(path, { method: 'DELETE' });
export function uploadFiles(files: File[], combine: boolean, onProgress: (n: number) => void, endpoint = '/api/documents/upload'): Promise<any> {
  return new Promise((resolve, reject) => {
    const send = (retried: boolean) => {
      const xhr = new XMLHttpRequest(); const form = new FormData();
      files.forEach(f => form.append('files', f)); form.append('combine', String(combine));
      xhr.open('POST', endpoint); xhr.withCredentials = true; xhr.setRequestHeader('X-CSRF-Token', csrf);
      if (sessionToken) xhr.setRequestHeader('X-Session-Token', sessionToken);
      xhr.upload.onprogress = e => { if (e.lengthComputable) onProgress(Math.round(e.loaded / e.total * 100)); };
      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) resolve(data);
          else if (xhr.status === 403 && data.error?.code === 'csrf_failed' && !retried) {
            refreshCsrf().then(ok => { if (ok) send(true); else reject(new ApiError(data.error?.code || 'upload_failed', data.error?.message || 'Upload failed.', xhr.status)); });
          } else reject(new ApiError(data.error?.code || 'upload_failed', data.error?.message || 'Upload failed.', xhr.status));
        } catch { reject(new ApiError('upload_failed', 'Upload failed.', xhr.status)); }
      };
      xhr.onerror = () => reject(new ApiError('network_error', 'Connection lost. Your selected files have not been uploaded.', 0));
      xhr.send(form);
    };
    send(false);
  });
}
export function bytes(value: number) { if (value < 1024) return `${value} B`; if (value < 1048576) return `${(value / 1024).toFixed(1)} KB`; if (value < 1073741824) return `${(value / 1024).toFixed(1)} MB`; return `${(value / 1073741824).toFixed(2)} GB`; }
export function date(value: string) { return new Date(value.endsWith('Z') ? value : value + 'Z').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }); }
export function dateTime(value: string) { return new Date(value.endsWith('Z') ? value : value + 'Z').toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
export async function waitForJob(id: string, onUpdate?: (j: any) => void) { for (;;) { const job = await api(`/api/jobs/${id}`); onUpdate?.(job); if (['completed', 'failed', 'cancelled'].includes(job.status)) return job; await new Promise(r => setTimeout(r, 900)); } }
export async function downloadUrl(url: string, filename?: string) { const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', headers: authHeaders(new Headers()) }); if (!response.ok) throw new ApiError('download_failed', 'Download failed or the export has expired.', response.status); const blob = await response.blob(); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename || url.split('/').pop() || 'download'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 10000); }
