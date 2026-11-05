'use client';
import { useState } from 'react';
import { Modal, Button, Field } from './ui';
import { useApp } from './providers';
import { patch, del } from '@/lib/api';
import type { Document } from '@/lib/types';
export function useDocumentActions(onChange: () => void) {
  const { t, notify } = useApp(); const [deleting, setDeleting] = useState<Document | null>(null); const [renaming, setRenaming] = useState<Document | null>(null); const [name, setName] = useState(''); const [busy, setBusy] = useState(false);
  const modals = <>{deleting && <Modal title={t('confirmDelete')} onClose={() => setDeleting(null)}><p>{t('deleteWarning')}</p><div className="inline-error" style={{ marginTop: 15 }}>{deleting.name}</div><div className="modal-actions"><Button onClick={() => setDeleting(null)}>{t('cancel')}</Button><Button variant="danger" loading={busy} onClick={async () => { setBusy(true); try { await del(`/api/documents/${deleting.id}`); setDeleting(null); notify(t('deleted')); onChange(); } catch (e: any) { notify(e.message, true); } finally { setBusy(false); } }}>{t('delete')}</Button></div></Modal>}{renaming && <Modal title={t('rename')} onClose={() => setRenaming(null)}><form onSubmit={async e => { e.preventDefault(); setBusy(true); try { await patch(`/api/documents/${renaming.id}`, { name }); setRenaming(null); notify(t('saveName')); onChange(); } catch (err: any) { notify(err.message, true); } finally { setBusy(false); } }}><Field label={t('filename')}><input value={name} onChange={e => setName(e.target.value)} maxLength={120} required /></Field><div className="modal-actions"><Button type="button" onClick={() => setRenaming(null)}>{t('cancel')}</Button><Button variant="primary" loading={busy}>{t('save')}</Button></div></form></Modal>}</>;
  return { confirmDelete: setDeleting, startRename: (d: Document) => { setName(d.name); setRenaming(d); }, modals };
}
