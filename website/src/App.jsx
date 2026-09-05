import { useEffect, useMemo, useRef, useState } from "react";
import "./App.scss";

const PROOFS = "/proofs";
const CATEGORIES = [
  ["serif", "Serif"],
  ["sans", "Sans Serif"],
  ["display", "Display"],
  ["italic", "Italic"],
  ["blackletter", "Blackletter"],
  ["wood", "Wood Type"],
];
const DEFAULT_TEXT = "";

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

// Each face's font is loaded once, on first sight, through the FontFace API.
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
      { rootMargin: "400px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [ref, visible]);
  return visible;
}

function fontFile(fonts) {
  return (fonts || []).find((f) => f.endsWith(".otf")) || (fonts || [])[0];
}

// Text in a face, with the characters the proto doesn't have yet shown gray
// instead of silently falling back to another font.
function Preview({ family, chars, text, size, className }) {
  const have = useMemo(() => new Set(chars || ""), [chars]);
  const runs = useMemo(() => {
    const out = [];
    for (const ch of text) {
      const ok = /\s/.test(ch) || have.has(ch);
      const last = out[out.length - 1];
      if (last && last.ok === ok) last.s += ch;
      else out.push({ ok, s: ch });
    }
    return out;
  }, [text, have]);
  return (
    <div className={className} style={{ fontFamily: `"${family}", Georgia, serif`, fontSize: `${size}px` }}>
      {runs.map((r, i) =>
        r.ok ? (
          <span key={i}>{r.s}</span>
        ) : (
          <span key={i} className="preview__missing" title="not in this font yet">
            {r.s}
          </span>
        ),
      )}
    </div>
  );
}

// -- index --------------------------------------------------------------------

const SORTS = {
  page: (a, b) => (a.pages[0] || 9999) - (b.pages[0] || 9999) || a.name.localeCompare(b.name),
  name: (a, b) => (a.title || a.name).localeCompare(b.title || b.name),
  glyphs: (a, b) => b.encoded - a.encoded || a.name.localeCompare(b.name),
  size: (a, b) => sizePt(b) - sizePt(a) || a.name.localeCompare(b.name),
};

function sizePt(f) {
  return Math.max(0, ...f.sizes.map((s) => parseInt(s, 10) || 0));
}

function previewText(face, mode, custom) {
  if (mode === "custom" && custom.trim()) return custom;
  if (mode === "alphabet") return face.chars || "";
  if (mode === "numerals") return [...(face.chars || "")].filter((c) => /\d/.test(c)).join("") || face.sample || "";
  return face.sample || face.title || face.family;
}

function Card({ face, mode, custom, size }) {
  const ref = useRef(null);
  const visible = useVisible(ref);
  const file = fontFile(face.fonts);
  useEffect(() => {
    if (visible) loadFont(face.family, file);
  }, [visible, face.family, file]);
  const text = previewText(face, mode, custom);
  const pages = face.pages.filter(Boolean);
  return (
    <a ref={ref} className="row" href={`#/face/${encodeURIComponent(face.name)}`}>
      <div className="row__side">
        <span className="row__name">{face.title || face.family}</span>
        <span className="row__meta">
          {face.encoded} glyphs · {face.sizes.length} size{face.sizes.length === 1 ? "" : "s"}
        </span>
        <span className="row__meta">
          {CATEGORIES.find(([k]) => k === face.category)?.[1] || face.category}
          {pages.length ? ` · p. ${pages[0]}` : ""}
          {" · "}
          <span className={`badge badge--${face.status}`}>v{face.version}</span>
        </span>
      </div>
      {visible ? (
        <Preview family={face.family} chars={face.chars} text={text} size={size} className="row__preview" />
      ) : (
        <div className="row__preview" style={{ fontSize: `${size}px` }}>
          {" "}
        </div>
      )}
    </a>
  );
}

function Filters({ filters, setFilters, counts }) {
  const toggle = (key, value) =>
    setFilters((f) => {
      const set = new Set(f[key]);
      if (set.has(value)) set.delete(value);
      else set.add(value);
      return { ...f, [key]: set };
    });
  return (
    <aside className="filters">
      <h3 className="filters__title">Categories</h3>
      {CATEGORIES.map(([key, label]) => (
        <label key={key} className="filters__row">
          <input type="checkbox" checked={filters.category.has(key)} onChange={() => toggle("category", key)} />
          <span className="filters__label">{label}</span>
          <span className="filters__count">{counts.category[key] || 0}</span>
        </label>
      ))}
      <h3 className="filters__title">Character set</h3>
      <label className="filters__row">
        <input type="checkbox" checked={filters.lower} onChange={() => setFilters((f) => ({ ...f, lower: !f.lower }))} />
        <span className="filters__label">Has lowercase</span>
        <span className="filters__count">{counts.lower}</span>
      </label>
      <label className="filters__row">
        <input
          type="checkbox"
          checked={filters.figures}
          onChange={() => setFilters((f) => ({ ...f, figures: !f.figures }))}
        />
        <span className="filters__label">Has figures</span>
        <span className="filters__count">{counts.figures}</span>
      </label>
      <h3 className="filters__title">Review</h3>
      <label className="filters__row">
        <input type="checkbox" checked={filters.clean} onChange={() => setFilters((f) => ({ ...f, clean: !f.clean }))} />
        <span className="filters__label">No warnings</span>
        <span className="filters__count">{counts.clean}</span>
      </label>
    </aside>
  );
}

function Index({ index, query }) {
  const [mode, setMode] = useState("specimen");
  const [custom, setCustom] = useState(DEFAULT_TEXT);
  const [size, setSize] = useState(56);
  const [sort, setSort] = useState("page");
  const [filters, setFilters] = useState({ category: new Set(), lower: false, figures: false, clean: false });
  const faces = useMemo(() => index.faces_list || [], [index]);
  const counts = useMemo(() => {
    const category = {};
    for (const f of faces) category[f.category] = (category[f.category] || 0) + 1;
    return {
      category,
      lower: faces.filter((f) => f.lower > 0).length,
      figures: faces.filter((f) => f.figures > 0).length,
      clean: faces.filter((f) => f.checks.warnings === 0).length,
    };
  }, [faces]);
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return faces
      .filter((f) => !q || `${f.name} ${f.title} ${f.family} ${f.series} ${f.sample}`.toLowerCase().includes(q))
      .filter((f) => filters.category.size === 0 || filters.category.has(f.category))
      .filter((f) => !filters.lower || f.lower > 0)
      .filter((f) => !filters.figures || f.figures > 0)
      .filter((f) => !filters.clean || f.checks.warnings === 0)
      .sort(SORTS[sort]);
  }, [faces, query, filters, sort]);
  const reset = () => {
    setMode("specimen");
    setCustom(DEFAULT_TEXT);
    setSize(56);
    setSort("page");
    setFilters({ category: new Set(), lower: false, figures: false, clean: false });
  };
  return (
    <>
      <div className="controls">
        <div className="controls__inner">
          <div className="segmented" role="tablist" aria-label="Preview">
            {[
              ["custom", "Custom"],
              ["specimen", "Specimen"],
              ["alphabet", "Alphabet"],
              ["numerals", "Numerals"],
            ].map(([k, label]) => (
              <button
                key={k}
                type="button"
                role="tab"
                aria-selected={mode === k}
                className={`segmented__item${mode === k ? " segmented__item--on" : ""}`}
                onClick={() => setMode(k)}
              >
                {label}
              </button>
            ))}
          </div>
          <input
            className="controls__text"
            type="text"
            value={custom}
            placeholder="Type something"
            spellCheck={false}
            onChange={(e) => {
              setCustom(e.target.value);
              setMode("custom");
            }}
          />
          <label className="controls__size">
            <span className="controls__value">{size}px</span>
            <input type="range" min="20" max="140" value={size} onChange={(e) => setSize(Number(e.target.value))} />
          </label>
          <select className="controls__sort" value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
            <option value="page">Sort by page</option>
            <option value="name">Sort by name</option>
            <option value="size">Sort by largest size</option>
            <option value="glyphs">Sort by most glyphs</option>
          </select>
          <button type="button" className="controls__reset" onClick={reset}>
            Reset
          </button>
        </div>
      </div>
      <div className="browse">
        <Filters filters={filters} setFilters={setFilters} counts={counts} />
        <section className="results">
          <p className="results__count">
            {shown.length} of {faces.length} faces · {index.encoded_glyphs} glyphs traced from the page
          </p>
          <div className="results__list">
            {shown.map((f) => (
              <Card key={f.name} face={f} mode={mode} custom={custom} size={size} />
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

// -- one family ---------------------------------------------------------------

function FontFaceStyle({ face }) {
  const file = fontFile(face.fonts);
  if (!file) return null;
  const css = `@font-face{font-family:"${face.family}";src:url("/fonts/${file}") format("opentype");font-display:block}`;
  return <style>{css}</style>;
}

function printed(l) {
  return l.printed || l.text;
}

function Tester({ face, chars }) {
  const covered = (face.specimen_lines || []).filter((l) => l.missing && l.missing.length === 0);
  const sample = covered.length ? printed(covered.reduce((a, b) => (printed(b).length > printed(a).length ? b : a))) : "ABC";
  const [text, setText] = useState(sample);
  const [size, setSize] = useState(120);
  const missing = useMemo(() => [...new Set([...text].filter((c) => !/\s/.test(c) && !chars.has(c)))], [text, chars]);
  return (
    <section className="tester">
      <div className="tester__bar">
        <input
          className="tester__input"
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type here to preview text"
          spellCheck={false}
        />
        <label className="tester__size">
          <span className="controls__value">{size}px</span>
          <input type="range" min="24" max="320" value={size} onChange={(e) => setSize(Number(e.target.value))} />
        </label>
      </div>
      <Preview family={face.family} chars={[...chars].join("")} text={text || " "} size={size} className="tester__output" />
      {missing.length > 0 && (
        <p className="tester__note">
          Not in this font yet: {missing.map((c) => `“${c}”`).join(" ")}. Version {face.version} has only what the
          specimen shows{face.glyphs.some((g) => g.constructed) ? ", plus constructed capitals" : ""}.
        </p>
      )}
    </section>
  );
}

function Family({ face }) {
  const src = face.source || {};
  const encoded = face.glyphs.filter((g) => g.encoded && g.char && g.char.trim());
  const chars = useMemo(() => new Set(encoded.map((g) => g.char)), [encoded]);
  const traced = encoded.filter((g) => !g.constructed).length;
  const constructed = encoded.filter((g) => g.constructed).length;
  const alternates = face.glyphs.filter((g) => g.alternate_of).length;
  const lines = Object.entries(face.lines || {});
  const coveredLines = (face.specimen_lines || []).filter((l) => l.proof && l.missing && l.missing.length === 0);
  const rGlyph = face.glyphs.find((g) => g.name === "R");
  const leafPages = face.leaf_pages || {};
  const where = (src.leaves || []).map((l) => (leafPages[l] ? `p. ${leafPages[l]}` : `leaf ${l}`)).join(", ");
  const readers = [...new Set((face.specimen_lines || []).map((l) => l.by || "human"))];
  const year = String(src.date || "").replace(/\D/g, "");
  const otf = face.fonts.find((f) => f.endsWith(".otf"));
  const ttf = face.fonts.find((f) => f.endsWith(".ttf"));

  return (
    <article className="family">
      <FontFaceStyle face={face} />
      <header className="family__header">
        <div>
          <h1 className="family__name">{face.title || face.family}</h1>
          <p className="family__source">
            {src.publisher}, {src.date} · <em>{(src.title || "").split(".")[0]}</em>, {where} ·{" "}
            <a className="link" href={src.url}>
              Internet Archive
            </a>
          </p>
        </div>
        <div className="family__actions">
          <span className={`badge badge--${face.status}`}>
            v{face.version} · {face.status}
          </span>
          {otf && (
            <a className="button" href={`/fonts/${otf}`} download>
              Download OTF
            </a>
          )}
          {ttf && (
            <a className="button button--quiet" href={`/fonts/${ttf}`} download>
              TTF
            </a>
          )}
        </div>
      </header>

      <Tester face={face} chars={chars} />

      <section className="family__section">
        <h2 className="family__h2">Styles</h2>
        <p className="family__caption">
          {encoded.length} glyphs: {traced} traced from the specimen
          {constructed > 0 ? `, ${constructed} constructed from them` : ""}.{" "}
          {alternates > 0 ? `${alternates} same-letter alternates from other sizes ride along unencoded. ` : ""}
          {readers.some((r) => r.includes("claude"))
            ? "The lines were read from the page by Claude and cross-checked against the archive's OCR."
            : ""}
        </p>
        {coveredLines.length > 0 && (
          <div className="styles">
            {coveredLines.map((l) => (
              <div key={`${l.leaf}-${l.band}`} className="styles__row">
                <div className="styles__label">
                  {l.line}
                  <span className="styles__sub">{l.by ? `read by ${l.by}` : ""}</span>
                </div>
                <Preview family={face.family} chars={[...chars].join("")} text={printed(l)} size={64} className="styles__preview" />
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="family__section">
        <h2 className="family__h2">Glyphs</h2>
        <p className="family__caption">
          {constructed > 0
            ? "Black letters are traced; gray ones are constructed from traced parts. "
            : "Every glyph is traced from the page. "}
          Each label names the specimen line the letter came from.
        </p>
        <figure className="figure">
          <img src={`${PROOFS}/${face.name}/proofs/alphabet.png`} alt="Every letter in the font, labeled by origin" />
        </figure>
      </section>

      {coveredLines.length > 0 && (
        <section className="family__section">
          <h2 className="family__h2">The specimen, re-set</h2>
          <p className="family__caption">
            Each line as printed{year ? ` in ${year}` : ""}, over the same words set in the revived font at the same cap
            height.
          </p>
          {coveredLines.map((l) => (
            <figure key={`${l.leaf}-${l.band}`} className="figure">
              <img src={`${PROOFS}/${face.name}/proofs/${l.proof}`} alt={`${printed(l)} — printed line over the re-set line`} loading="lazy" />
              <figcaption>
                {printed(l)} · {l.line}
              </figcaption>
            </figure>
          ))}
        </section>
      )}

      <section className="family__section">
        <h2 className="family__h2">About</h2>
        <p className="family__caption">
          A revival of {src.publisher}&rsquo;s <strong>{face.series || face.title}</strong> from the printed
          specimen, never from digital font software. Every glyph carries its leaf, line and pixel box inside the
          font (the PHFD table). Fonts mature in versions like software: proto (traced, machine-spaced), draft
          (reviewed), release (spaced, kerned, cleaned).
        </p>
        {lines.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Size</th>
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
        )}
      </section>

      {face.arrow_attempts && face.arrow_attempts.length > 0 && (
        <section className="family__section">
          <h2 className="family__h2">Scan vs. trace</h2>
          <p className="family__caption">
            Gray: the scan. Cyan: potrace, the control trace that made the font. Magenta: Arrow, Quiver&rsquo;s model.
            Black where all agree. Arrow was shown the R twice and both times drew a picture of it rather than its
            edge.
          </p>
          <div className="research">
            <figure className="figure figure--overlay">
              <img src={`${PROOFS}/${face.name}/proofs/R__overlay.png`} alt="Overlay of scan, potrace and Arrow traces of the R" />
            </figure>
            <table className="table">
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
                      <a className="link" href={`${PROOFS}/${face.name}/glyphs/R_.png`}>cut R</a>
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
                      <a className="link" href={`${PROOFS}/${face.name}/${a.kept_as}`}>svg</a>
                    </td>
                    <td>
                      <a className="link" href={`${PROOFS}/${face.name}/${a.input}`}>
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

function FamilyPage({ name, index }) {
  const { face, error } = useFace(name);
  const list = (index && index.faces_list) || [];
  const i = list.findIndex((f) => f.name === name);
  const prev = i > 0 ? list[i - 1] : null;
  const next = i >= 0 && i < list.length - 1 ? list[i + 1] : null;
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [name]);
  return (
    <div className="page">
      <nav className="crumbs">
        <a className="link" href="#/">
          ← All faces
        </a>
        <span className="crumbs__spacer" />
        {prev && (
          <a className="link" href={`#/face/${encodeURIComponent(prev.name)}`}>
            ← {prev.title || prev.name}
          </a>
        )}
        {next && (
          <a className="link" href={`#/face/${encodeURIComponent(next.name)}`}>
            {next.title || next.name} →
          </a>
        )}
      </nav>
      {error && <p className="app__error">Could not load {name}: {error}</p>}
      {face ? <Family face={face} /> : !error && <p className="app__loading">Loading {name}…</p>}
    </div>
  );
}

// -- app ----------------------------------------------------------------------

function App() {
  const { index, error } = useIndex();
  const route = useHash();
  const [query, setQuery] = useState("");
  return (
    <div className="app">
      <header className="topbar">
        <a className="topbar__brand" href="#/">
          Phantom Foundry
        </a>
        {!route.face && (
          <input
            className="topbar__search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search faces"
            spellCheck={false}
            aria-label="Search faces"
          />
        )}
        <span className="topbar__tag">Public domain typefaces revived from specimen books</span>
      </header>
      {error && <p className="app__error">Could not load the index: {error}</p>}
      {route.face ? (
        <FamilyPage name={route.face} index={index} />
      ) : index ? (
        <Index index={index} query={query} />
      ) : (
        !error && <p className="app__loading">Loading…</p>
      )}
      <footer className="footer">
        Letters are cut from the scan and traced with potrace; every step is kept; fonts mature in versions — proto,
        draft, release — like software. Fonts: SIL Open Font License. Tooling: MIT.{" "}
        <a className="link" href="https://github.com/romellogoodman/phantom-foundry">
          Source
        </a>
      </footer>
    </div>
  );
}

export default App;
