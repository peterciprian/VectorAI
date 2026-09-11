'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { getTranslations, type Locale } from '../../lib/i18n';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const defaultLocale: Locale = 'en';

type LegendItem = {
  id: string;
  code: string;
  name: string;
  geometry_type: 'Polygon' | 'LineString' | 'Point';
  color_rgb: number[];
  color_tolerance: number;
  enabled: boolean;
};

export default function LegendPage() {
  const [locale, setLocale] = useState<Locale>(defaultLocale);
  const [projectId, setProjectId] = useState('');
  const [items, setItems] = useState<LegendItem[]>([]);
  const [bbox, setBbox] = useState([0, 0, 0, 0]);
  const [cropSize, setCropSize] = useState({ width: 800, height: 500 });
  const cropFrame = useRef<HTMLDivElement>(null);
  const dragState = useRef<{ mode: 'move' | 'resize'; handle?: string; startX: number; startY: number; startBbox: number[] } | null>(null);
  const [status, setStatus] = useState<'loading' | 'pending' | 'ready' | 'saving' | 'saved' | 'error'>('loading');
  const content = getTranslations(locale);

  useEffect(() => {
    const savedLocale = window.localStorage.getItem('vectoryai-locale');
    if (savedLocale === 'en' || savedLocale === 'hu') setLocale(savedLocale);
    const id = new URLSearchParams(window.location.search).get('project') || '';
    setProjectId(id);
    if (!id) return;
    fetch(`${apiBase}/api/v1/projects/${id}/legend`)
      .then((response) => response.json())
      .then((result) => {
        setItems(result.items || []);
        setBbox(result.legend_bbox || [0, 0, 0, 0]);
        setStatus(result.status === 'pending' ? 'pending' : 'ready');
      })
      .catch(() => setStatus('error'));
  }, []);

  function updateItem(index: number, field: keyof LegendItem, value: string | number | boolean) {
    setItems((current) => current.map((item, currentIndex) => currentIndex === index ? { ...item, [field]: value } as LegendItem : item));
  }

  function addItem() {
    setItems((current) => [...current, { id: `custom_${Date.now()}`, code: 'NEW', name: '', geometry_type: 'Polygon', color_rgb: [128, 128, 128], color_tolerance: 18, enabled: true }]);
    setStatus('ready');
  }

  function beginCropDrag(event: React.PointerEvent<HTMLElement>, mode: 'move' | 'resize', handle?: string) {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragState.current = { mode, handle, startX: event.clientX, startY: event.clientY, startBbox: bbox };
  }

  function updateCropDrag(event: React.PointerEvent<HTMLDivElement>) {
    const drag = dragState.current;
    if (!drag || !cropFrame.current) return;
    const bounds = cropFrame.current.getBoundingClientRect();
    const scaleX = cropSize.width / bounds.width;
    const scaleY = cropSize.height / bounds.height;
    const dx = (event.clientX - drag.startX) * scaleX;
    const dy = (event.clientY - drag.startY) * scaleY;
    const [startX, startY, startRight, startBottom] = drag.startBbox;
    let next = [startX, startY, startRight, startBottom];
    if (drag.mode === 'move') next = [startX + dx, startY + dy, startRight + dx, startBottom + dy];
    if (drag.handle?.includes('w')) next[0] = startX + dx;
    if (drag.handle?.includes('e')) next[2] = startRight + dx;
    if (drag.handle?.includes('n')) next[1] = startY + dy;
    if (drag.handle?.includes('s')) next[3] = startBottom + dy;
    const width = Math.max(20, next[2] - next[0]);
    const height = Math.max(20, next[3] - next[1]);
    next[2] = next[0] + width;
    next[3] = next[1] + height;
    setBbox(next.map((value) => Math.round(value)));
  }

  function endCropDrag() {
    dragState.current = null;
  }

  async function saveLegend() {
    setStatus('saving');
    const response = await fetch(`${apiBase}/api/v1/projects/${projectId}/legend`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items }) });
    setStatus(response.ok ? 'saved' : 'error');
  }

  async function detectLegend() {
    const hasCrop = bbox[2] > bbox[0] && bbox[3] > bbox[1];
    const response = await fetch(`${apiBase}/api/v1/projects/${projectId}/legend/detect`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(hasCrop ? { bbox } : {}) });
    if (response.ok) setStatus('pending');
  }

  return (
    <main className="legend-page">
      <nav className="nav shell-width" aria-label={content.navigation.main}>
        <Link className="brand" href="/"><span className="brand-mark">V</span> VectoryAI</Link>
        <div className="nav-links"><Link className="back-link" href={`/viewer?project=${projectId}`}>&#8592; {content.legend.back}</Link><label className="language-picker"><span className="sr-only">{content.language.label}</span><select value={locale} onChange={(event) => { setLocale(event.target.value as Locale); window.localStorage.setItem('vectoryai-locale', event.target.value); }} aria-label={content.language.label}><option value="en">EN</option><option value="hu">HU</option></select></label></div>
      </nav>
      <section className="legend-shell shell-width">
        <div className="legend-heading"><p className="eyebrow"><span className="eyebrow-dot" /> {content.legend.eyebrow}</p><h1>{content.legend.titleBefore}<br /><em>{content.legend.titleEmphasis}</em></h1><p className="lede">{content.legend.description}</p></div>
        {status === 'loading' && <p className="upload-hint">{content.viewer.loading}</p>}
        {status === 'pending' && <p className="upload-hint">{content.legend.pending}</p>}
        {status === 'error' && <p className="upload-error">{content.legend.error}</p>}
        {(status === 'ready' || status === 'saving' || status === 'saved') && <>
          <div className="legend-actions"><button className="button button-primary" type="button" onClick={saveLegend} disabled={status === 'saving'}>{status === 'saving' ? content.legend.saving : content.legend.save} <span aria-hidden="true">&#8599;</span></button><button className="text-link" type="button" onClick={detectLegend}>{content.legend.detect} &#8599;</button><button className="text-link" type="button" onClick={addItem}>{content.legend.add} &#43;</button>{status === 'saved' && <span className="upload-success">{content.legend.saved}</span>}</div>
          <fieldset className="legend-bbox"><legend>{content.legend.bbox}</legend><p className="legend-bbox-hint">{content.legend.bboxHint}</p><div className="legend-crop-preview" ref={cropFrame} style={{ backgroundImage: `url(${apiBase}/api/v1/projects/${projectId}/thumbnail)` }} onPointerMove={updateCropDrag} onPointerUp={endCropDrag}><div className="legend-crop-frame" style={{ left: `${(bbox[0] / cropSize.width) * 100}%`, top: `${(bbox[1] / cropSize.height) * 100}%`, width: `${((bbox[2] - bbox[0]) / cropSize.width) * 100}%`, height: `${((bbox[3] - bbox[1]) / cropSize.height) * 100}%` }} onPointerDown={(event) => beginCropDrag(event, 'move')}>{['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'].map((handle) => <span key={handle} className={`legend-crop-handle handle-${handle}`} onPointerDown={(event) => { event.stopPropagation(); beginCropDrag(event, 'resize', handle); }} />)}</div></div><div>{bbox.map((value, index) => <input key={index} aria-label={`${content.legend.bbox} ${index + 1}`} type="number" value={value} onChange={(event) => setBbox((current) => current.map((item, currentIndex) => currentIndex === index ? Number(event.target.value) : item))} />)}</div></fieldset>
          <div className="legend-table" role="table" aria-label={content.legend.eyebrow}><div className="legend-row legend-header"><span>{content.legend.code}</span><span>{content.legend.name}</span><span>{content.legend.geometry}</span><span>{content.legend.tolerance}</span><span>{content.legend.enabled}</span><span /></div>{items.map((item, index) => <div className="legend-row" key={item.id}><input aria-label={content.legend.code} value={item.code} onChange={(event) => updateItem(index, 'code', event.target.value)} /><input aria-label={content.legend.name} value={item.name} onChange={(event) => updateItem(index, 'name', event.target.value)} /><select aria-label={content.legend.geometry} value={item.geometry_type} onChange={(event) => updateItem(index, 'geometry_type', event.target.value)}><option value="Polygon">{content.legend.polygon}</option><option value="LineString">{content.legend.line}</option><option value="Point">{content.legend.point}</option></select><input aria-label={content.legend.tolerance} type="range" min="0" max="100" value={item.color_tolerance} onChange={(event) => updateItem(index, 'color_tolerance', Number(event.target.value))} /><input aria-label={content.legend.enabled} type="checkbox" checked={item.enabled} onChange={(event) => updateItem(index, 'enabled', event.target.checked)} /><button type="button" onClick={() => setItems((current) => current.filter((_, currentIndex) => currentIndex !== index))}>{content.legend.remove}</button></div>)}</div>
        </>}
      </section>
    </main>
  );
}
