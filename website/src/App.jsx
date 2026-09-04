import { useEffect, useMemo, useRef, useState } from "react";
import "./App.scss";

const PROOFS = "/proofs";

// -- data -------------------------------------------------------------------

function useIndex() {
  const [index, setIndex] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetch(`${PROOFS}/index.json`)
      .then((r) => r.json())
      .then((d) => !cancelled && setIndex(d))
      .catch((e) => !cancelled && setError(String(e)));
    return () => {
      cancelled = true;
    };
  }, []);
  return { index, error };
}

function useFace(name) {
  // state is keyed by the face it belongs to, so switching faces shows
  // "loading" without a synchronous reset inside the effect
  const [state, setState] = useState({ name: null, face: null, error: null });
  useEffect(() => {
    let cancelled = false;
    if (!name) return undefined;
    fetch(`${PROOFS}/${name}/proofs/face.json`)
      .then((r) => r.json())
      .then((d) => !cancelled && setState({ name, face: d, error: null }))
      .catch((e) => !cancelled && setState({ name, face: null, error: String(e) }));
    return () => {
      cancelled = true;
    };
  }, [name]);
  return state.name === name ? { face: state.face, error: state.error } : { face: null, error: null };
}

function useHash() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const m = hash.match(/^#\/face\/([^/?]+)/);
  return { face: m ? decodeURIComponent(m[1]) : null };
}

// A face's font is loaded once, on first use, through the FontFace API —
// the index shows a hundred faces without a hundred @font-face rules up front.
const loaded = new Set();
function loadFont(family, file) {
  if (!file || loaded.has(family)) return;
  loaded.add(family);
  const ff = new FontFace(family, `url("/fonts/${file}")`, { display: "swap" });
  ff.load()
    .then((f) => document.fonts.add(f))
    .catch(() => loaded.delete(family));
}

function useVisible(ref) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || visible) return undefined;
    const io = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting) && setVisible(true),
      { rootMargin: "300px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [ref, visible]);
  return visible;
}

function fontFile(fonts) {
  return (fonts || []).find((f) => f.endsWith(".otf")) || (fonts || [])[0];
}

// -- index --------------------------------------------------------------------

const SORTS = {
  name: (a, b) => a.name.localeCompare(b.name),
  glyphs: (a, b) => b.encoded - a.encoded || a.name.localeCompare(b.name),
  page: (a, b) => (a.pages[0] || 9999) - (b.pages[0] || 9999) || a.name.localeCompare(b.name),
  warnings: (a, b) => b.checks.warnings - a.checks.warnings || a.name.localeCompare(b.name),
};

function Card({ face }) {
  const ref = useRef(null);
  const visible = useVisible(ref);
  const file = fontFile(face.fonts);
  useEffect(() => {
    if (visible) loadFont(face.family, file);
  }, [visible, face.family, file]);
  const pages = face.pages.filter(Boolean);
  return (
    <a ref={ref} className="card" href={`#/face/${encodeURIComponent(face.name)}`}>
      <div className="card__specimen" style={{ fontFamily: `"${face.family}", serif` }}>
        {visible ? face.sample || face.title || face.family : " "}
      </div>
      <h2 className="card__title">
        {face.title || face.family}
        <span className={`face__badge face__badge--${face.status}`}>
          v{face.version} · {face.status}
        </span>
      </h2>
      <p className="card__meta">
        {face.encoded} glyphs · {face.caps}A {face.lower}a {face.figures}1
        {face.constructed > 0 ? ` · ${face.constructed} constructed` : ""}
        {face.sizes.length > 0 ? ` · ${face.sizes.join(" ")}` : ""}
        {pages.length > 0 ? ` · p. ${pages.join(", ")}` : ""}
        {face.checks.warnings > 0 ? ` · ${face.checks.warnings} warnings` : ""}
      </p>
    </a>
  );
}

function Index({ index }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("page");
  const faces = useMemo(() => index.faces_list || [], [index]);
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return faces
      .filter((f) => !q || `${f.name} ${f.title} ${f.family} ${f.series} ${f.sample}`.toLowerCase().includes(q))
      .sort(SORTS[sort]);
  }, [faces, query, sort]);
  return (
    <section className="index">
      <div className="index__controls">
        <label className="tester__field index__search">
          <span className="tester__label">Find a face</span>
          <input
            className="tester__input"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="name, series, or the words on the page"
            spellCheck={false}
          />
        </label>
        <label className="tester__field">
          <span className="tester__label">Sort</span>
          <select className="tester__input index__select" value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="page">By page in the book</option>
            <option value="name">By name</option>
            <option value="glyphs">Most glyphs first</option>
            <option value="warnings">Warnings first</option>
          </select>
        </label>
      </div>
      <p className="index__count">
        {shown.length} of {faces.length} faces · {index.encoded_glyphs} glyphs traced from the page
      </p>
      <div className="index__grid">
        {shown.map((f) => (
          <Card key={f.name} face={f} />
        ))}
      </div>
    </section>
  );
}

// -- one face -----------------------------------------------------------------

function FontFaceStyle({ face }) {
  const file = fontFile(face.fonts);
  if (!file) return null;
  const css = `@font-face{font-family:"${face.family}";src:url("/fonts/${file}") format("opentype");font-display:block}`;
  return <style>{css}</style>;
}

function Tester({ face }) {
  const covered = (face.specimen_lines || []).filter((l) => l.missing && l.missing.length === 0);
  const printed = (l) => l.printed || l.text;
  const sample = covered.length
    ? printed(covered.reduce((a, b) => (printed(b).length > printed(a).length ? b : a)))
    : "ABC";
  const [text, setText] = useState(sample);
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
        {text || " "}
      </div>
      {missing.length > 0 && (
        <p className="tester__note">
          Not in this font yet: {missing.map((c) => `“${c}”`).join(" ")} — v{face.version} has only what the
          specimen shows{face.glyphs.some((g) => g.constructed) ? ", plus constructed capitals" : ""}.
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
  const leafPages = face.leaf_pages || {};
  const where = (src.leaves || [])
    .map((l) => (leafPages[l] ? `p. ${leafPages[l]}` : `leaf ${l}`))
    .join(", ");
  const readers = [...new Set((face.specimen_lines || []).map((l) => l.by || "human"))];
  const year = String(src.date || "").replace(/\D/g, "");

  return (
    <article className="face">
      <FontFaceStyle face={face} />
      <header className="face__header">
        <h2 className="face__family">
          {face.title || face.family}{" "}
          <span className={`face__badge face__badge--${face.status}`}>
            v{face.version} · {face.status}
          </span>
        </h2>
        <p className="face__source">
          {src.publisher}, {src.date} — <em>{(src.title || "").split(".")[0]}</em>, {where}.{" "}
          <a className="face__link" href={src.url}>
            Internet Archive ↗
          </a>
        </p>
        <p className="face__detail">
          {encoded.length} glyphs: {traced} traced from the specimen
          {constructed > 0 ? `, ${constructed} constructed from them` : ""}.{" "}
          {alternates > 0 ? `${alternates} same-letter alternates from other sizes ride along unencoded. ` : ""}
          {readers.some((r) => r.includes("claude"))
            ? "The lines were read from the page by Claude and cross-checked against the archive's OCR. "
            : ""}
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
            Each line as printed{year ? ` in ${year}` : ""}, and the same words set in the revived font at the same
            cap height.
          </p>
          {coveredLines.map((l) => (
            <figure key={`${l.leaf}-${l.band}`} className="face__figure">
              <img
                src={`${PROOFS}/${face.name}/proofs/${l.proof}`}
                alt={`${l.printed || l.text} — printed line over the re-set line`}
                loading="lazy"
              />
              <figcaption>
                {l.printed || l.text} — {l.line}
                {l.by ? ` · read by ${l.by}` : ""}
              </figcaption>
            </figure>
          ))}
        </section>
      )}

      <section className="face__section">
        <h3 className="face__subhead">Alphabet</h3>
        <p className="face__caption">
          {constructed > 0
            ? "Black letters are traced; gray ones are constructed from traced parts (E without its foot is F, M upside down is W). "
            : "Every glyph is traced from the page. "}
          Each label names the specimen line the letter came from.
        </p>
        <figure className="face__figure">
          <img src={`${PROOFS}/${face.name}/proofs/alphabet.png`} alt="Every letter in the font, labeled by origin" />
        </figure>
      </section>

      {lines.length > 0 && (
        <section className="face__section">
          <h3 className="face__subhead">{lines.length} sizes, one face</h3>
          <p className="face__caption">
            The page shows the design at {lines.length} sizes, each cut separately. Scaled to a common cap height,
            the sizes differ in weight — measured here as stem width over cap height.
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
                  <td>{m.glyphs ? m.glyphs.length : m.n_caps}</td>
                  <td>{Math.round(m.cap_height_px)}</td>
                  <td>{m.stem_units ?? "—"}</td>
                  <td>{m.stem_units ? `${((m.stem_units / face.metrics.cap_height) * 100).toFixed(1)}%` : "—"}</td>
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
              <img src={`${PROOFS}/${face.name}/proofs/R__overlay.png`} alt="Overlay of scan, potrace and Arrow traces of the R" />
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
                      <a className="face__link" href={`${PROOFS}/${face.name}/glyphs/R_.png`}>cut R</a>
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

function FacePage({ name, index }) {
  const { face, error } = useFace(name);
  const list = (index && index.faces_list) || [];
  const i = list.findIndex((f) => f.name === name);
  const prev = i > 0 ? list[i - 1] : null;
  const next = i >= 0 && i < list.length - 1 ? list[i + 1] : null;
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [name]);
  return (
    <>
      <nav className="nav">
        <a className="nav__link" href="#/">
          ← All faces
        </a>
        <span className="nav__spacer" />
        {prev && (
          <a className="nav__link" href={`#/face/${encodeURIComponent(prev.name)}`}>
            ← {prev.title || prev.name}
          </a>
        )}
        {next && (
          <a className="nav__link" href={`#/face/${encodeURIComponent(next.name)}`}>
            {next.title || next.name} →
          </a>
        )}
      </nav>
      {error && <p className="app__error">Could not load {name}: {error}</p>}
      {face ? <Face face={face} /> : !error && <p className="app__loading">Loading {name}…</p>}
    </>
  );
}

// -- app ----------------------------------------------------------------------

function App() {
  const { index, error } = useIndex();
  const route = useHash();
  return (
    <main className="app">
      <header className="app__header">
        <h1 className="app__title">
          <a className="app__home" href="#/">
            Phantom Foundry
          </a>
        </h1>
        <p className="app__tagline">
          Public domain typefaces revived from scanned specimen books. Letters are cut from the scan and traced
          with potrace; the letters the book doesn&rsquo;t show are built from the ones it does; every step is kept.
          Fonts mature in versions — proto, draft, release — like software.
        </p>
      </header>
      {error && <p className="app__error">Could not load the index: {error}</p>}
      {route.face ? (
        <FacePage name={route.face} index={index} />
      ) : index ? (
        <Index index={index} />
      ) : (
        !error && <p className="app__loading">Loading…</p>
      )}
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
