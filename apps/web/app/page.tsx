'use client';

import { useEffect, useState } from 'react';
import { getTranslations, type Locale } from '../lib/i18n';

const defaultLocale: Locale = 'en';

export default function Home() {
  const [locale, setLocale] = useState<Locale>(defaultLocale);
  const copy = getTranslations(locale);

  useEffect(() => {
    const savedLocale = window.localStorage.getItem('vectoryai-locale');
    if (savedLocale === 'en' || savedLocale === 'hu') setLocale(savedLocale);
  }, []);

  function handleLocaleChange(nextLocale: Locale) {
    setLocale(nextLocale);
    window.localStorage.setItem('vectoryai-locale', nextLocale);
  }

  return (
    <main>
      <nav className="nav shell-width" aria-label={copy.navigation.main}>
        <a className="brand" href="#top"><span className="brand-mark">V</span> VectoryAI</a>
        <div className="nav-links">
          <a href="#workflow">{copy.navigation.workflow}</a>
          <a href="#outcomes">{copy.navigation.why}</a>
          <a className="nav-cta" href="#start">{copy.navigation.start} <span aria-hidden="true">&#8599;</span></a>
          <label className="language-picker">
            <span className="sr-only">{copy.language.label}</span>
            <select value={locale} onChange={(event) => handleLocaleChange(event.target.value as Locale)} aria-label={copy.language.label}>
              <option value="en">EN</option>
              <option value="hu">HU</option>
            </select>
          </label>
        </div>
      </nav>

      <section className="hero shell-width" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-dot" /> {copy.hero.eyebrow}</p>
          <h1>{copy.hero.titleBefore} <em>{copy.hero.titleEmphasis}</em></h1>
          <p className="lede">{copy.hero.description}</p>
          <div className="hero-actions">
            <a className="button button-primary" href="#start">{copy.hero.create} <span aria-hidden="true">&#8599;</span></a>
            <a className="text-link" href="#workflow">{copy.hero.learn} <span aria-hidden="true">&#8595;</span></a>
          </div>
        </div>
        <div className="map-art" aria-label={copy.hero.mapLabel} role="img">
          <div className="map-toolbar"><span>{copy.hero.plan}</span><span>{copy.hero.projection}</span></div>
          <div className="map-grid" />
          <div className="map-road road-one" /><div className="map-road road-two" /><div className="map-road road-three" />
          <div className="map-zone zone-one" /><div className="map-zone zone-two" /><div className="map-zone zone-three" />
          <div className="map-label label-one">Lk-1</div><div className="map-label label-two">Vt</div>
          <div className="map-pin pin-one" /><div className="map-pin pin-two" />
          <div className="map-caption"><span className="caption-line" /> {copy.hero.caption}</div>
        </div>
      </section>
      <section className="outcomes shell-width" id="outcomes" aria-label={copy.outcomes.ariaLabel}>
        <p className="section-kicker">{copy.outcomes.kicker}</p>
        <div className="outcome-grid">
          {copy.outcomes.metrics.map(({ value, label }) => <div className="outcome" key={label}><strong>{value}</strong><span>{label}</span></div>)}
          <p className="outcome-note">{copy.outcomes.note}</p>
        </div>
      </section>

      <section className="workflow-section shell-width" id="workflow">
        <div className="section-heading">
          <p className="section-kicker">{copy.workflow.kicker}</p>
          <h2>{copy.workflow.titleBefore}<br /><em>{copy.workflow.titleEmphasis}</em></h2>
        </div>
        <div className="workflow">
          {copy.workflow.steps.map((step) => <article className="workflow-card" key={step.number}>
            <span className="step-number">{step.number}</span>
            <div><h3>{step.title}</h3><p>{step.body}</p></div>
            <span className="step-arrow" aria-hidden="true">&#8599;</span>
          </article>)}
        </div>
      </section>

      <section className="closing shell-width" id="start">
        <div><p className="eyebrow"><span className="eyebrow-dot" /> {copy.closing.eyebrow}</p><h2>{copy.closing.titleBefore}<br /><em>{copy.closing.titleEmphasis}</em></h2></div>
        <div className="closing-side"><p>{copy.closing.description}</p><a className="button button-light" href="mailto:peterciprian@gmail.com">{copy.closing.cta} <span aria-hidden="true">&#8599;</span></a></div>
      </section>
    </main>
  );
}
