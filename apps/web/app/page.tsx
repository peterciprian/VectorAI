'use client';

import { useEffect, useState } from 'react';
import { getTranslations, type Locale } from '../lib/i18n';

const defaultLocale: Locale = 'en';

export default function Home() {
  const [locale, setLocale] = useState<Locale>(defaultLocale);
  const content = getTranslations(locale);

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
      <nav className="nav shell-width" aria-label={content.navigation.main}>
        <a className="brand" href="#top"><span className="brand-mark">V</span> VectoryAI</a>
        <div className="nav-links">
          <a href="#workflow">{content.navigation.workflow}</a>
          <a href="#outcomes">{content.navigation.why}</a>
          <a className="nav-cta" href="#start">{content.navigation.start} <span aria-hidden="true">&#8599;</span></a>
          <label className="language-picker">
            <span className="sr-only">{content.language.label}</span>
            <select value={locale} onChange={(event) => handleLocaleChange(event.target.value as Locale)} aria-label={content.language.label}>
              <option value="en">EN</option>
              <option value="hu">HU</option>
            </select>
          </label>
        </div>
      </nav>

      <section className="hero shell-width" id="top">
        <div className="hero-content">
          <p className="eyebrow"><span className="eyebrow-dot" /> {content.hero.eyebrow}</p>
          <h1>{content.hero.titleBefore} <em>{content.hero.titleEmphasis}</em></h1>
          <p className="lede">{content.hero.description}</p>
          <div className="hero-actions">
            <a className="button button-primary" href="#start">{content.hero.create} <span aria-hidden="true">&#8599;</span></a>
            <a className="text-link" href="#workflow">{content.hero.learn} <span aria-hidden="true">&#8595;</span></a>
          </div>
        </div>
        <div className="map-art" aria-label={content.hero.mapLabel} role="img">
          <div className="map-toolbar"><span>{content.hero.plan}</span><span>{content.hero.projection}</span></div>
          <div className="map-grid" />
          <div className="map-road road-one" /><div className="map-road road-two" /><div className="map-road road-three" />
          <div className="map-zone zone-one" /><div className="map-zone zone-two" /><div className="map-zone zone-three" />
          <div className="map-label label-one">Zkk</div><div className="map-label label-two">Lke-1</div><div className="map-label label-three">Vt-3</div>
          <div className="map-pin pin-one" /><div className="map-pin pin-two" />
          <div className="map-caption"><span className="caption-line" /> {content.hero.caption}</div>
        </div>
      </section>
      <section className="outcomes shell-width" id="outcomes" aria-label={content.outcomes.ariaLabel}>
        <p className="section-kicker">{content.outcomes.kicker}</p>
        <div className="outcome-grid">
          {content.outcomes.metrics.map(({ value, label }) => <div className="outcome" key={label}><strong>{value}</strong><span>{label}</span></div>)}
          <p className="outcome-note">{content.outcomes.note}</p>
        </div>
      </section>

      <section className="workflow-section shell-width" id="workflow">
        <div className="section-heading">
          <p className="section-kicker">{content.workflow.kicker}</p>
          <h2>{content.workflow.titleBefore}<br /><em>{content.workflow.titleEmphasis}</em></h2>
        </div>
        <div className="workflow">
          {content.workflow.steps.map((step) => <article className="workflow-card" key={step.number}>
            <span className="step-number">{step.number}</span>
            <div><h3>{step.title}</h3><p>{step.body}</p></div>
            <span className="step-arrow" aria-hidden="true">&#8599;</span>
          </article>)}
        </div>
      </section>

      <section className="closing shell-width" id="start">
        <div><p className="eyebrow"><span className="eyebrow-dot" /> {content.closing.eyebrow}</p><h2>{content.closing.titleBefore}<br /><em>{content.closing.titleEmphasis}</em></h2></div>
        <div className="closing-side"><p>{content.closing.description}</p><a className="button button-light" href="mailto:peterciprian@gmail.com">{content.closing.cta} <span aria-hidden="true">&#8599;</span></a></div>
      </section>
    </main>
  );
}
