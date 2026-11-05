import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Login } from '@/components/login';
import { Preview } from '@/components/preview';
import { DocumentCard, Progress, StatusBadge } from '@/components/ui';
import ScanPage from '@/app/scan/page';
import { post, uploadFiles, setCsrf, api } from '@/lib/api';

vi.mock('@/components/providers', () => ({ useApp: () => ({ t: (k: string) => k, notify: vi.fn(), refresh: vi.fn(), session: { authenticated: false } }), ScanLogo: () => <svg /> }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => '/dashboard' }));
vi.mock('@/lib/api', async () => { const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api'); return { ...actual, post: vi.fn(), uploadFiles: vi.fn() }; });
const page: any = { id: 'p1', status: 'completed', original_url: '/api/pages/p1/file?kind=original', processed_url: '/api/pages/p1/file?kind=processed', width: 700, height: 900, error: '' };
const doc: any = { id: 'd1', name: 'Mietvertrag_Essen_2026', created_at: '2026-11-05T10:00:00Z', page_count: 2, status: 'completed', size_bytes: 1024, document_type: 'image', thumbnail_url: null };
beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());
describe('Authentication', () => {
  it('renders owner sign-in without public registration', () => { render(<Login />); expect(screen.getByLabelText('username')).toBeInTheDocument(); expect(screen.getByLabelText('password')).toBeInTheDocument(); expect(screen.queryByText(/create account/i)).not.toBeInTheDocument(); expect(screen.getByRole('button', { name: 'signIn' })).toBeInTheDocument(); });
  it('submits credentials to the real API client', async () => { vi.mocked(post).mockResolvedValue({ authenticated: true }); render(<Login />); fireEvent.change(screen.getByLabelText('username'), { target: { value: 'owner' } }); fireEvent.change(screen.getByLabelText('password'), { target: { value: 'secret' } }); fireEvent.click(screen.getByRole('button', { name: 'signIn' })); await waitFor(() => expect(post).toHaveBeenCalledWith('/api/auth/login', { username: 'owner', password: 'secret', totp_code: '' })); });
});
describe('Upload interface', () => {
  it('accepts multiple files and invokes the upload API', async () => { vi.mocked(uploadFiles).mockResolvedValue({ documents: [{ id: 'd1' }] }); const { container } = render(<ScanPage />); const input = container.querySelector('input[type="file"]') as HTMLInputElement; const file = new File(['image'], 'page.png', { type: 'image/png' }); fireEvent.change(input, { target: { files: [file] } }); expect(screen.getByText('page.png')).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: /Upload 1 file/ })); await waitFor(() => expect(uploadFiles).toHaveBeenCalled()); });
});
describe('Document preview', () => {
  it('shows original and processed images and a comparison slider', () => { const { rerender } = render(<Preview page={page} mode="original" zoom={1} fit editing={false} corners={[]} onCorners={vi.fn()} onZoom={vi.fn()} />); expect(screen.getByAltText('Original document')).toHaveAttribute('src', page.original_url); rerender(<Preview page={page} mode="processed" zoom={1} fit editing={false} corners={[]} onCorners={vi.fn()} onZoom={vi.fn()} />); expect(screen.getByAltText('OmniFix processed document')).toHaveAttribute('src', page.processed_url); rerender(<Preview page={page} mode="compare" zoom={1} fit editing={false} corners={[]} onCorners={vi.fn()} onZoom={vi.fn()} />); expect(screen.getByRole('slider', { name: /Before and after/ })).toBeInTheDocument(); });
});
describe('Page management and export actions', () => {
  it('exposes rename, delete and export actions', () => { const onRename = vi.fn(), onDelete = vi.fn(); render(<DocumentCard doc={doc} onRename={onRename} onDelete={onDelete} />); fireEvent.click(screen.getByRole('button', { name: /rename/ })); expect(onRename).toHaveBeenCalledWith(doc); fireEvent.click(screen.getByRole('button', { name: /delete/ })); expect(onDelete).toHaveBeenCalledWith(doc); expect(screen.getByRole('link', { name: 'export' }).getAttribute('href')).toMatch(/^\/export\/?\?id=d1$/); });
  it('renders accessible progress and status', () => { render(<><Progress value={65} /><StatusBadge status="completed" /></>); expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '65'); expect(screen.getByText('completed')).toBeInTheDocument(); });
});
describe('API security', () => {
  it('sends CSRF and same-origin credentials on mutations', async () => { const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) }); vi.stubGlobal('fetch', fetchMock); setCsrf('token-123'); await api('/api/settings', { method: 'PATCH', body: JSON.stringify({ theme: 'dark' }) }); const options = fetchMock.mock.calls[0][1]; expect(options.credentials).toBe('same-origin'); expect(options.headers.get('X-CSRF-Token')).toBe('token-123'); });
});
