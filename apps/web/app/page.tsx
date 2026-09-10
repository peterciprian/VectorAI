const workflow = [
  { number: '01', title: 'Bring in the plan', body: 'Upload a high-resolution PDF, TIFF, JPG, or PNG and keep the original sheet intact.' },
  { number: '02', title: 'Anchor it in EOV', body: 'Place ground control points against a reference layer or the default OpenStreetMap view.' },
  { number: '03', title: 'Teach the legend', body: 'Review detected classes, colors, and geometry types before the model starts tracing.' },
  { number: '04', title: 'Export clean layers', body: 'Inspect the result, correct what matters, and download strict GIS-ready Shapefile layers.' }
];

const outcomes = [
  ['70-80%', 'less manual tracing'],
  ['90%+', 'target geometric IoU'],
  ['0', 'illegal overlaps or slivers']
];

export default function Home() {
  return (
    <main>
      <nav className="nav shell-width" aria-label="Main navigation">
        <a className="brand" href="#top"><span className="brand-mark">V</span> VectoryAI</a>
        <div className="nav-links">
          <a href="#workflow">Workflow</a>
          <a href="#outcomes">Why VectoryAI</a>
          <a className="nav-cta" href="#start">Start a project <span aria-hidden="true">&#8599;</span></a>
        </div>
      </nav>

      <section className="hero shell-width" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-dot" /> AI-assisted urban plan vectorization</p>
          <h1>From scanned plan to <em>spatial intelligence.</em></h1>
          <p className="lede">VectoryAI helps urban planners turn legacy zoning and master plans into accurate, editable GIS layers without tracing every boundary by hand.</p>
          <div className="hero-actions">
            <a className="button button-primary" href="#start">Create a project <span aria-hidden="true">&#8599;</span></a>
            <a className="text-link" href="#workflow">See how it works <span aria-hidden="true">&#8595;</span></a>
          </div>
        </div>
        <div className="map-art" aria-label="Abstract preview of an urban plan map" role="img">
          <div className="map-toolbar"><span>PLAN / 047</span><span>EPSG:23700</span></div>
          <div className="map-grid" />
          <div className="map-road road-one" /><div className="map-road road-two" /><div className="map-road road-three" />
          <div className="map-zone zone-one" /><div className="map-zone zone-two" /><div className="map-zone zone-three" />
          <div className="map-label label-one">Lk-1</div><div className="map-label label-two">Vt</div>
          <div className="map-pin pin-one" /><div className="map-pin pin-two" />
          <div className="map-caption"><span className="caption-line" /> georeferenced plan preview</div>
        </div>
      </section>
      <section className="outcomes shell-width" id="outcomes" aria-label="Project outcomes">
        <p className="section-kicker">Built for the work behind the map</p>
        <div className="outcome-grid">
          {outcomes.map(([value, label]) => <div className="outcome" key={label}><strong>{value}</strong><span>{label}</span></div>)}
          <p className="outcome-note">A focused workspace for municipalities, planning offices, and GIS teams managing the next revision.</p>
        </div>
      </section>

      <section className="workflow-section shell-width" id="workflow">
        <div className="section-heading">
          <p className="section-kicker">A considered path from raster to vector</p>
          <h2>Keep the judgement.<br /><em>Lose the busywork.</em></h2>
        </div>
        <div className="workflow">
          {workflow.map((step) => <article className="workflow-card" key={step.number}>
            <span className="step-number">{step.number}</span>
            <div><h3>{step.title}</h3><p>{step.body}</p></div>
            <span className="step-arrow" aria-hidden="true">&#8599;</span>
          </article>)}
        </div>
      </section>

      <section className="closing shell-width" id="start">
        <div><p className="eyebrow"><span className="eyebrow-dot" /> The first revision starts here</p><h2>Make your next plan<br /><em>ready for GIS.</em></h2></div>
        <div className="closing-side"><p>Digitize zoning districts, regulatory lines, and point symbols in one traceable workflow. Native EOV support included.</p><a className="button button-light" href="mailto:peterciprian@gmail.com">Talk to the team <span aria-hidden="true">&#8599;</span></a></div>
      </section>
    </main>
  );
}
