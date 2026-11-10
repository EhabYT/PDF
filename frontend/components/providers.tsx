'use client';
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api, post, setCsrf, setSessionToken } from '@/lib/api';
import { translate } from '@/lib/i18n';
import type { SessionInfo, Prefs } from '@/lib/types';
import { AppShell } from './shell';
import { Login } from './login';
import { Loader2, CheckCircle2, AlertCircle, X } from 'lucide-react';

interface Toast { id: number; message: string; error?: boolean }
interface Context { session: SessionInfo | null; prefs: Prefs | null; refresh: () => Promise<void>; refreshPrefs: () => Promise<void>; t: (key: string) => string; notify: (message: string, error?: boolean) => void; logout: () => Promise<void>; }
const AppContext = createContext<Context>(null!);
export const useApp = () => useContext(AppContext);
export function Providers({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [loading, setLoading] = useState(true);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const notify = useCallback((message: string, error = false) => { const id = Date.now() + Math.random(); setToasts(t => [...t, { id, message, error }]); setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 5500); }, []);
  const refresh = useCallback(async () => { const s = await api<SessionInfo>('/api/auth/session'); setCsrf(s.csrf_token); setSessionToken(s.session_token); setSession(s); if (s.authenticated) { try { setPrefs(await api<Prefs>('/api/settings')); } catch { setPrefs(null); } } else setPrefs(null); }, []);
  const refreshPrefs = useCallback(async () => { setPrefs(await api<Prefs>('/api/settings')); }, []);
  useEffect(() => { refresh().catch(() => notify('Could not reach the private server. Check your connection.', true)).finally(() => setLoading(false)); if ('serviceWorker' in navigator && process.env.NODE_ENV === 'production') navigator.serviceWorker.register('/sw.js').catch(() => {}); }, [refresh, notify]);
  useEffect(() => {
    const theme = prefs?.theme || 'system';
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => document.documentElement.dataset.theme = theme === 'system' ? (media.matches ? 'dark' : 'light') : theme;
    apply(); media.addEventListener('change', apply);
    document.documentElement.lang = prefs?.language || 'en'; document.documentElement.dir = prefs?.language === 'ar' ? 'rtl' : 'ltr';
    return () => media.removeEventListener('change', apply);
  }, [prefs?.theme, prefs?.language]);
  const t = useCallback((key: string) => translate(prefs?.language || 'en', key), [prefs?.language]);
  const logout = async () => { try { await post('/api/auth/logout'); } finally { await refresh(); window.location.href = '/'; } };
  return <AppContext.Provider value={{ session, prefs, refresh, refreshPrefs, t, notify, logout }}>
    {loading ? <div className="boot-screen"><div className="brand-mark large"><ScanLogo /></div><Loader2 className="animate-spin" size={22} /><span>{translate('en', 'loading')}</span></div> : !session?.authenticated ? <Login /> : <AppShell>{children}</AppShell>}
    <div className="toast-stack" aria-live="polite">{toasts.map(toast => <div key={toast.id} className={`toast ${toast.error ? 'error' : ''}`}>{toast.error ? <AlertCircle size={19} /> : <CheckCircle2 size={19} />}<span>{toast.message}</span><button aria-label="Dismiss" onClick={() => setToasts(t => t.filter(x => x.id !== toast.id))}><X size={16} /></button></div>)}</div>
  </AppContext.Provider>;
}
export function ScanLogo() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3"/><path d="M7 12h10M9 8h6M9 16h6"/></svg>; }
