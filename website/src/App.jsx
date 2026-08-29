import "./App.scss";

const faces = [
  {
    slug: "wood-class-l",
    family: "Wood Class L",
    source: "Barnhart Bros. & Spindler, Specimen Book No. 9 (Chicago, 1907)",
    detail: "Wood type No. 266 — Class L, fifteen-line. Leaf 895.",
    archive: "https://archive.org/details/bookoftypespecim00barnrich",
    glyphs: "R",
    sample: "R",
    attempts: [
      { engine: "potrace", iou: 0.993, note: "control trace" },
      { engine: "arrow-1.1 · attempt 1", iou: 0.79, note: "filled slab + hairline outline" },
      { engine: "arrow-1.1 · attempt 2", iou: 0.855, note: "square framing; R on an invented plinth" },
    ],
  },
];

function Face({ face }) {
  return (
    <article className="face">
      <header className="face__header">
        <h2 className="face__family">{face.family}</h2>
        <p className="face__source">{face.source}</p>
        <p className="face__detail">
          {face.detail}{" "}
          <a className="face__link" href={face.archive}>
            Internet Archive ↗
          </a>
        </p>
      </header>

      <div className="face__specimen" style={{ fontFamily: `"${face.family}"` }}>
        <span className="face__glyph face__glyph--display">{face.sample}</span>
        <div className="face__waterfall">
          {[160, 96, 64, 40, 24].map((size) => (
            <span key={size} className="face__glyph" style={{ fontSize: `${size}px` }}>
              {face.sample}
            </span>
          ))}
        </div>
      </div>

      <section className="face__research">
        <h3 className="face__subhead">Scan vs. trace</h3>
        <figure className="face__figure">
          <img
            src={`/proofs/${face.slug}/${face.glyphs}_overlay.png`}
            alt="Overlay of scan, potrace and Arrow traces"
          />
          <figcaption>
            Gray: the 1907 scan. Cyan: potrace control trace. Magenta: Arrow. Black where all agree.
          </figcaption>
        </figure>
        <table className="face__table">
          <thead>
            <tr>
              <th>Engine</th>
              <th>IoU vs. scan</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {face.attempts.map((a) => (
              <tr key={a.engine}>
                <td>{a.engine}</td>
                <td>{a.iou.toFixed(3)}</td>
                <td>{a.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </article>
  );
}

function App() {
  return (
    <main className="app">
      <header className="app__header">
        <h1 className="app__title">Phantom Foundry</h1>
        <p className="app__tagline">
          Public domain typefaces revived from scanned specimen books — traced with Quiver&rsquo;s
          Arrow model, checked against potrace, compiled from UFO sources.
        </p>
      </header>
      {faces.map((face) => (
        <Face key={face.slug} face={face} />
      ))}
      <footer className="app__footer">
        Fonts: SIL Open Font License. Tooling: MIT.{" "}
        <a className="face__link" href="https://github.com/romellogoodman/phantom-foundry">
          Source ↗
        </a>
      </footer>
    </main>
  );
}

export default App;
