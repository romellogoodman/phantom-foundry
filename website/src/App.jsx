import { useEffect, useMemo, useState } from "react";
import "./App.scss";

const PROOFS = "/proofs";

function useFaces() {
  const [faces, setFaces] = useState([]);
  const [error, setError] = useState(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const index = await (await fetch(`${PROOFS}/index.json`)).json();
        const loaded = await Promise.all(
          index.faces.map(async (slug) => (await fetch(`${PROOFS}/${slug}/proofs/face.json`)).json()),
        );
        if (!cancelled) setFaces(loaded);
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  return { faces, error };
}

function FontFace({ face }) {
  const file = face.fonts.find((f) => f.endsWith(".otf")) || face.fonts[0];
  if (!file) return null;
  const css = `@font-face{font-family:"${face.family}";src:url("/fonts/${file}") format("opentype");font-display:block}`;
  return <style>{css}</style>;
}

function Tester({ face }) {
  const [text, setText] = useState("RECORD");
  const [size, setSize] = useState(160);
  const encoded = useMemo(() => new Set(face.glyphs.filter((g) => g.encoded).map((g) => g.char)), [face]);
  const missing = useMemo(
    () => [...new Set([...text].filter((c) => !/\s/.test(c) && !encoded.has(c)))],
    [text, encoded],
  );
  return (
    <section className="tester">
      <div className="tester__controls">
        <label className="tester__field">
          <span className="tester__label">Type</span>
          <input
            className="tester__input"
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type something"
            spellCheck={false}
          />
        </label>
        <label className="tester__field tester__field--size">
          <span className="tester__label">
            Size <span className="tester__value">{size}px</span>
          </span>
          <input
            className="tester__slider"
            type="range"
            min="24"
            max="400"
            value={size}
            onChange={(e) => setSize(Number(e.target.value))}
          />
        </label>
      </div>
      <div
        className="tester__output"
        style={{ fontFamily: `"${face.family}"`, fontSize: `${size}px` }}
        aria-live="polite"
      >
        {text || " "}
      </div>
      {missing.length > 0 && (
        <p className="tester__note">
          Not in this font yet: {missing.map((c) => `“${c}”`).join(" ")} — v{face.version} has capitals only.
        </p>
      )}
    </section>
  );
}

function Face({ face }) {
  const src = face.source || {};
  const encoded = face.glyphs.filter((g) => g.encoded && g.char && g.char.trim());
  const traced = encoded.filter((g) => !g.constructed).length;
  const constructed = encoded.filter((g) => g.constructed).length;
  const alternates = face.glyphs.filter((g) => g.alternate_of).length;
  const lines = Object.entries(face.lines || {});
  const coveredLines = (face.specimen_lines || []).filter((l) => l.proof && l.missing && l.missing.length === 0);
  const rGlyph = face.glyphs.find((g) => g.name === "R");

  return (
    <article className="face">
      <FontFace face={face} />
      <header className="face__header">
        <h2 className="face__family">
          {face.family}{" "}
          <span className={`face__badge face__badge--${face.status}`}>
            v{face.version} · {face.status}
          </span>
        </h2>
        <p className="face__source">
          {src.publisher}, {src.date} — <em>{(src.title || "").split(".")[0]}</em>, leaf {(src.leaves || []).join(", ")}.{" "}
          <a className="face__link" href={src.url}>
            Internet Archive ↗
          </a>
        </p>
        <p className="face__detail">
          {encoded.length} letters: {traced} traced from the specimen, {constructed} constructed from them.{" "}
          {alternates} same-letter alternates from other sizes ride along unencoded.{" "}
          {face.fonts.map((f) => (
            <a key={f} className="face__link" href={`/fonts/${f}`} download>
              {f} ↓
            </a>
          ))}
        </p>
      </header>

      <Tester face={face} />

      {coveredLines.length > 0 && (
        <section className="face__section">
          <h3 className="face__subhead">The specimen, re-set</h3>
          <p className="face__caption">
            Each line as printed in 1907, and the same words set in the revived font at the same cap height.
          </p>
          {coveredLines.map((l) => (
            <figure key={l.line} className="face__figure">
              <img src={`${PROOFS}/${face.name}/proofs/${l.proof}`} alt={`${l.text} — printed line over the re-set line`} />
              <figcaption>
                {l.text} — {l.line}-line
              </figcaption>
            </figure>
          ))}
        </section>
      )}

      <section className="face__section">
        <h3 className="face__subhead">Alphabet</h3>
        <p className="face__caption">
          Black letters are traced; gray ones are constructed from traced parts (E without its foot is F, M upside
          down is W). Each label names the specimen line the letter came from.
        </p>
        <figure className="face__figure">
          <img src={`${PROOFS}/${face.name}/proofs/alphabet.png`} alt="Every letter in the font, labeled by origin" />
        </figure>
      </section>

      {lines.length > 0 && (
        <section className="face__section">
          <h3 className="face__subhead">Four sizes, one face</h3>
          <p className="face__caption">
            The page shows the design at four sizes, each a separate set of wood blocks. Scaled to a common cap
            height, the smaller cuts are bolder.
          </p>
          <table className="face__table">
            <thead>
              <tr>
                <th>Line</th>
                <th>Letters</th>
                <th>Cap height (px)</th>
                <th>Stem (units)</th>
                <th>Stem / cap</th>
              </tr>
            </thead>
            <tbody>
              {lines.map(([key, m]) => (
                <tr key={key}>
                  <td>{key.split(":")[1]}</td>
                  <td>{m.n_caps}</td>
                  <td>{Math.round(m.cap_height_px)}</td>
                  <td>{m.stem_units}</td>
                  <td>{((m.stem_units / face.metrics.cap_height) * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {face.arrow_attempts && face.arrow_attempts.length > 0 && (
        <section className="face__section">
          <h3 className="face__subhead">Scan vs. trace</h3>
          <p className="face__caption">
            Gray: the scan. Cyan: potrace, the control trace that made the font. Magenta: Arrow, Quiver&rsquo;s model.
            Black where all agree. Arrow was shown the R twice and both times drew a picture of it rather than its
            edge — a slab with an outline on top, then a proper R on an invented plinth.
          </p>
          <div className="face__research">
            <figure className="face__figure face__figure--overlay">
              <img src={`${PROOFS}/${face.name}/proofs/R_overlay.png`} alt="Overlay of scan, potrace and Arrow traces of the R" />
            </figure>
            <table className="face__table">
              <thead>
                <tr>
                  <th>Trace</th>
                  <th>Input</th>
                  <th>IoU vs. scan</th>
                  <th>Best shape</th>
                  <th>Contours</th>
                </tr>
              </thead>
              <tbody>
                {rGlyph && rGlyph.diff && (
                  <tr>
                    <td>potrace</td>
                    <td>
                      <a className="face__link" href={`${PROOFS}/${face.name}/glyphs/R.png`}>cut R</a>
                    </td>
                    <td>{rGlyph.diff.potrace_iou_scan.toFixed(3)}</td>
                    <td>—</td>
                    <td>{rGlyph.diff.potrace_contours}</td>
                  </tr>
                )}
                {face.arrow_attempts.map((a) => (
                  <tr key={a.task_id}>
                    <td>
                      {a.model} · attempt {a.attempt}{" "}
                      <a className="face__link" href={`${PROOFS}/${face.name}/${a.kept_as}`}>svg</a>
                    </td>
                    <td>
                      <a className="face__link" href={`${PROOFS}/${face.name}/${a.input}`}>
                        {a.input.split("/").pop()}
                      </a>
                    </td>
                    <td>{a.iou_scan != null ? a.iou_scan.toFixed(3) : "—"}</td>
                    <td>{a.best_region_iou_scan != null ? a.best_region_iou_scan.toFixed(3) : "—"}</td>
                    <td>{a.contours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </article>
  );
}

function App() {
  const { faces, error } = useFaces();
  return (
    <main className="app">
      <header className="app__header">
        <h1 className="app__title">Phantom Foundry</h1>
        <p className="app__tagline">
          Public domain typefaces revived from scanned specimen books. Letters are cut from the scan and traced
          with potrace; the letters the book doesn&rsquo;t show are built from the ones it does; every step is kept.
          Fonts mature in versions — proto, draft, release — like software.
        </p>
      </header>
      {error && <p className="app__error">Could not load faces: {error}</p>}
      {faces.map((face) => (
        <Face key={face.name} face={face} />
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
