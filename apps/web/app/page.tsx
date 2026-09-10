const workflow = ['Ingest plan', 'Georeference in EOV', 'Review legend', 'Vectorize layers'];

export default function Home() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">VectoryAI / urban plan workspace</p>
        <h1>Turn legacy plans into usable GIS layers.</h1>
        <p className="lede">
          The platform foundation is ready for raster ingestion, EOV calibration, legend review, and traceable vector export.
        </p>
        <button type="button">Create a project</button>
      </section>
      <section className="workflow" aria-label="Processing workflow">
        {workflow.map((step, index) => (
          <article key={step}>
            <span>0{index + 1}</span>
            <h2>{step}</h2>
            <p>Planned in the MVP workflow.</p>
          </article>
        ))}
      </section>
    </main>
  );
}
