'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
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

  async function saveLegend() {
    setStatus('saving');
    const response = await fetch(`${apiBase}/api/v1/projects/${projectId}/legend`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items }) });
    setStatus(response.ok ? 'saved' : 'error');
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
          <div className="legend-actions"><button className="button button-primary" type="button" onClick={saveLegend} disabled={status === 'saving'}>{status === 'saving' ? content.legend.saving : content.legend.save} <span aria-hidden="true">&#8599;</span></button><button className="text-link" type="button" onClick={addItem}>{content.legend.add} &#43;</button>{status === 'saved' && <span className="upload-success">{content.legend.saved}</span>}</div>
          <div className="legend-table" role="table" aria-label={content.legend.eyebrow}><div className="legend-row legend-header"><span>{content.legend.code}</span><span>{content.legend.name}</span><span>{content.legend.geometry}</span><span>{content.legend.tolerance}</span><span>{content.legend.enabled}</span><span /></div>{items.map((item, index) => <div className="legend-row" key={item.id}><input aria-label={content.legend.code} value={item.code} onChange={(event) => updateItem(index, 'code', event.target.value)} /><input aria-label={content.legend.name} value={item.name} onChange={(event) => updateItem(index, 'name', event.target.value)} /><select aria-label={content.legend.geometry} value={item.geometry_type} onChange={(event) => updateItem(index, 'geometry_type', event.target.value)}><option value="Polygon">{content.legend.polygon}</option><option value="LineString">{content.legend.line}</option><option value="Point">{content.legend.point}</option></select><input aria-label={content.legend.tolerance} type="range" min="0" max="100" value={item.color_tolerance} onChange={(event) => updateItem(index, 'color_tolerance', Number(event.target.value))} /><input aria-label={content.legend.enabled} type="checkbox" checked={item.enabled} onChange={(event) => updateItem(index, 'enabled', event.target.checked)} /><button type="button" onClick={() => setItems((current) => current.filter((_, currentIndex) => currentIndex !== index))}>{content.legend.remove}</button></div>)}</div>
        </>}
      </section>
    </main>
  );
}
