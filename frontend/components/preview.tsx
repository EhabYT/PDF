'use client';
import { useState } from 'react';
import { FileImage, Loader2, AlertCircle, MoveHorizontal } from 'lucide-react';
import { CornerEditor } from './corner-editor';
import { useApp } from './providers';
import type { Page } from '@/lib/types';
export type PreviewMode = 'original' | 'processed' | 'compare' | 'side';
export function Preview({ page, mode, zoom, fit, editing, corners, onCorners, onZoom }: { page: Page; mode: PreviewMode; zoom: number; fit: boolean; editing: boolean; corners: number[][]; onCorners: (c: number[][]) => void; onZoom: (z: number) => void }) {
  const { t } = useApp(); const [split, setSplit] = useState(50);
  const src = mode === 'original' || editing ? page.original_url : page.processed_url;
  if (!src) return <div className="preview-placeholder">{page.status === 'failed' ? <AlertCircle size={38} /> : page.status === 'processing' || page.status === 'queued' ? <Loader2 size={38} className="animate-spin" /> : <FileImage size={38} />}<h3>{page.status === 'failed' ? t('failed') : t(page.status)}</h3><p>{page.error || 'The OmniFix preview will appear here when processing is complete.'}</p></div>;
  if ((mode === 'compare' || mode === 'side') && !page.processed_url) return <div className="preview-placeholder"><Loader2 size={32} className="animate-spin" /><p>Process this page to compare it with the original.</p></div>;
  return <div className={`preview-stage ${fit && zoom === 1 ? 'fit' : ''}`}>
    {mode === 'compare' ? <div className="compare-container" style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}><img src={page.original_url} alt="Original document" draggable={false} /><div className="compare-after" style={{ clipPath: `inset(0 0 0 ${split}%)` }}><img src={page.processed_url!} alt="OmniFix processed document" draggable={false} /></div><div className="compare-labels"><span>{t('original')}</span><span>OmniFix</span></div><div className="compare-divider" style={{ left: `${split}%` }}><span><MoveHorizontal size={17} /></span></div><input className="compare-range" type="range" min={0} max={100} value={split} onChange={e => setSplit(Number(e.target.value))} aria-label="Before and after comparison position" /></div> : mode === 'side' ? <div className="side-compare" style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}><figure><img src={page.original_url} alt="Original document" /><figcaption>{t('original')}</figcaption></figure><figure><img src={page.processed_url!} alt="OmniFix processed document" /><figcaption>OmniFix</figcaption></figure></div> : <div className="preview-paper" style={fit && zoom === 1 ? undefined : { width: `${Math.min(100, 85 * zoom)}%`, minWidth: zoom > 1 ? `${85 * zoom}%` : undefined }}><img src={src} alt={editing ? 'Original document with adjustable corners' : mode === 'original' ? 'Original document' : 'OmniFix processed document'} draggable={false} />{editing && <CornerEditor corners={corners} onChange={onCorners} onZoom={onZoom} zoom={zoom} />}</div>}
  </div>;
}
