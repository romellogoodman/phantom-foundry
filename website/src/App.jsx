import { useEffect, useMemo, useRef, useState } from "react";
import "@fontsource-variable/libre-franklin";
import "./App.scss";

const PROOFS = "/proofs";
const CATEGORIES = [
  ["serif", "Serif"],
  ["sans", "Sans serif"],
  ["display", "Display"],
  ["italic", "Italic"],
  ["blackletter", "Blackletter"],
  ["wood", "Wood type"],
];
const DEFAULT_TEXT = "";
const DEFAULT_SIZE = 72;
const REPO = "https://github.com/romellogoodman/phantom-foundry";

// A specimen book names a size the way its caption does: "72 Point", "Fifteen Line".
function sizeLabel(line) {
  if (!line) return "";
  const pt = String(line).match(/^(\d+)pt$/);
  if (pt) return `${pt[1]} Point`;
  return `${line[0].toUpperCase()}${line.slice(1)} Line`;
}

const READERS = { claude: "Claude", "claude+ocr": "Claude, checked against the archive’s OCR", human: "a person" };


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
    .then((f) => {
      document.fonts.add(f);
      // fonts added by hand fire no "loadingdone"; useMeanAdvance listens for this
      document.dispatchEvent(new CustomEvent("facefont", { detail: family }));
    })
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

// The mean advance of a face's capitals (or lowercase), in em, once its font is
// in: the width an absent letter's box takes, so a box in a condensed face is
// condensed too. Null until the font loads; the stylesheet has a default.
function useMeanAdvance(family, chars) {
  const [mean, setMean] = useState(null);
  useEffect(() => {
    let live = true;
    const measure = () => {
      if (!live || !document.fonts.check(`100px "${family}"`)) return;
      const ctx = document.createElement("canvas").getContext("2d");
      ctx.font = `100px "${family}"`;
      const em = (set) => (set.length ? ctx.measureText(set.join("")).width / set.length / 100 : null);
      const all = [...(chars || "")];
      const upper = em(all.filter((c) => !/\p{Ll}/u.test(c)));
      const lower = em(all.filter((c) => /\p{Ll}/u.test(c)));
      setMean({ upper: upper || lower, lower: lower || upper });
    };
    measure();
    document.fonts.addEventListener("loadingdone", measure);
    document.addEventListener("facefont", measure);
    return () => {
      live = false;
      document.fonts.removeEventListener("loadingdone", measure);
      document.removeEventListener("facefont", measure);
    };
  }, [family, chars]);
  return mean;
}

// Text in a face, with each character the proto doesn't have yet shown as an
// empty box at cap height (x-height for lowercase) instead of silently falling
// back to another font.
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
  const mean = useMeanAdvance(family, chars);
  return (
    <div
      className={className}
      style={{
        fontFamily: `"${family}", Georgia, serif`,
        fontSize: `${size}px`,
        ...(mean?.upper && { "--missing-upper": `${mean.upper.toFixed(3)}em`, "--missing-lower": `${mean.lower.toFixed(3)}em` }),
      }}
    >
      {runs.map((r, i) =>
        r.ok ? (
          <span key={i}>{r.s}</span>
        ) : (
          [...r.s].map((ch, j) => (
            <span
              key={`${i}-${j}`}
              className={`preview__missing${/\p{Ll}/u.test(ch) ? " preview__missing--lower" : ""}`}
              title={`“${ch}” is not in this font yet`}
              role="img"
              aria-label={`${ch} (not in this font yet)`}
            />
          ))
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
  // a face with no fully covered line shows its letters, not its name in boxes
  return face.sample || face.chars || face.title || face.family;
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
      <div className="row__head">
        <span className="row__name">{face.title || face.family}</span>
        {face.status !== "proto" && <span className={`status status--${face.status}`}>{face.status}</span>}
        <span className="row__meta">{face.encoded} letters</span>
        <span className="row__meta">{pages.length ? `page ${pages[0]}` : ""}</span>
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

function Toggle({ on, onClick, children, count }) {
  return (
    <button type="button" className={`toggle${on ? " toggle--on" : ""}`} aria-pressed={on} onClick={onClick}>
      {children}
      <span className="toggle__count">{count}</span>
    </button>
  );
}

function Filters({ filters, setFilters, counts }) {
  const toggleCategory = (value) =>
    setFilters((f) => {
      const set = new Set(f.category);
      if (set.has(value)) set.delete(value);
      else set.add(value);
      return { ...f, category: set };
    });
  return (
    <div className="filters" role="group" aria-label="Filter faces">
      {CATEGORIES.map(([key, label]) => (
        <Toggle key={key} on={filters.category.has(key)} onClick={() => toggleCategory(key)} count={counts.category[key] || 0}>
          {label}
        </Toggle>
      ))}
      <span className="filters__gap" />
      <Toggle on={filters.lower} onClick={() => setFilters((f) => ({ ...f, lower: !f.lower }))} count={counts.lower}>
        With lowercase
      </Toggle>
      <Toggle on={filters.figures} onClick={() => setFilters((f) => ({ ...f, figures: !f.figures }))} count={counts.figures}>
        With figures
      </Toggle>
    </div>
  );
}

const MODES = [
  ["specimen", "As printed"],
  ["alphabet", "Alphabet"],
  ["numerals", "Figures"],
];

function Index({ index, query }) {
  const [mode, setMode] = useState("specimen");
  const [custom, setCustom] = useState(DEFAULT_TEXT);
  const [size, setSize] = useState(DEFAULT_SIZE);
  const [sort, setSort] = useState("page");
  const [filters, setFilters] = useState({ category: new Set(), lower: false, figures: false });
  const faces = useMemo(() => index.faces_list || [], [index]);
  const counts = useMemo(() => {
    const category = {};
    for (const f of faces) category[f.category] = (category[f.category] || 0) + 1;
    return {
      category,
      lower: faces.filter((f) => f.lower > 0).length,
      figures: faces.filter((f) => f.figures > 0).length,
    };
  }, [faces]);
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return faces
      .filter((f) => !q || `${f.name} ${f.title} ${f.family} ${f.series} ${f.sample}`.toLowerCase().includes(q))
      .filter((f) => filters.category.size === 0 || filters.category.has(f.category))
      .filter((f) => !filters.lower || f.lower > 0)
      .filter((f) => !filters.figures || f.figures > 0)
      .sort(SORTS[sort]);
  }, [faces, query, filters, sort]);
  const changed =
    mode !== "specimen" || custom !== DEFAULT_TEXT || size !== DEFAULT_SIZE || sort !== "page" ||
    filters.category.size > 0 || filters.lower || filters.figures;
  const reset = () => {
    setMode("specimen");
    setCustom(DEFAULT_TEXT);
    setSize(DEFAULT_SIZE);
    setSort("page");
    setFilters({ category: new Set(), lower: false, figures: false });
  };
  return (
    <>
      <div className="intro">
        <p className="intro__lead">
          Phantom Foundry is an open-source type foundry. It revives typefaces from old specimen books, the catalogs
          printers once ordered their type from, by tracing the letters off the scanned page.
        </p>
        <p className="intro__note">
          Every font here is made from print, never from another font file, and all of the work is public: the tools
          that cut and trace the letters, every trace and proof along the way, and the fonts themselves. The fonts are
          under the SIL Open Font License and the code is MIT. Read it, fork it or fix a letter on{" "}
          <a className="link" href={REPO}>
            GitHub
          </a>
          .
        </p>
        <p className="intro__note">
          The first book is Barnhart Brothers &amp; Spindler&rsquo;s Specimen Book No. 9, printed in Chicago in 1907,
          with {faces.length} faces so far. They are early versions, numbered like software. Each has only the letters
          its page shows, and a letter it lacks appears as an empty box.
        </p>
      </div>
      <div className="controls">
        <div className="controls__modes" role="tablist" aria-label="Preview text">
          {MODES.map(([k, label]) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={mode === k}
              className={`toggle${mode === k ? " toggle--on" : ""}`}
              onClick={() => setMode(k)}
            >
              {label}
            </button>
          ))}
        </div>
        <input
          className="field controls__text"
          type="text"
          value={custom}
          placeholder="or type your own words"
          spellCheck={false}
          aria-label="Your own preview text"
          onChange={(e) => {
            setCustom(e.target.value);
            setMode(e.target.value.trim() ? "custom" : "specimen");
          }}
        />
        <label className="sizer">
          <span className="sizer__value">{size} px</span>
          <input type="range" min="20" max="160" value={size} onChange={(e) => setSize(Number(e.target.value))} />
        </label>
        <select className="field controls__sort" value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Order">
          <option value="page">In page order</option>
          <option value="name">By name</option>
          <option value="size">Largest size first</option>
          <option value="glyphs">Most letters first</option>
        </select>
      </div>
      <div className="browse">
        <div className="browse__bar">
          <Filters filters={filters} setFilters={setFilters} counts={counts} />
          <span className="browse__count">
            {shown.length === faces.length ? `${faces.length} faces` : `${shown.length} of ${faces.length} faces`}
          </span>
          {changed && (
            <button type="button" className="toggle" onClick={reset}>
              Reset
            </button>
          )}
        </div>
        {shown.length === 0 ? (
          <p className="browse__empty">No face matches. Clear the search or reset the filters.</p>
        ) : (
          <div className="browse__list">
            {shown.map((f) => (
              <Card key={f.name} face={f} mode={mode} custom={custom} size={size} />
            ))}
          </div>
        )}
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
  const [size, setSize] = useState(140);
  const missing = useMemo(() => [...new Set([...text].filter((c) => !/\s/.test(c) && !chars.has(c)))], [text, chars]);
  return (
    <section className="tester">
      <div className="tester__bar">
        <input
          className="field tester__input"
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type to try the font"
          aria-label="Text to set in this font"
          spellCheck={false}
        />
        <label className="sizer">
          <span className="sizer__value">{size} px</span>
          <input type="range" min="24" max="360" value={size} onChange={(e) => setSize(Number(e.target.value))} />
        </label>
      </div>
      <Preview family={face.family} chars={[...chars].join("")} text={text || " "} size={size} className="tester__output" />
      {missing.length > 0 && (
        <p className="tester__note">
          The specimen never shows {missing.map((c) => `“${c}”`).join(" ")}, so this font doesn&rsquo;t have{" "}
          {missing.length === 1 ? "it" : "them"} yet.
        </p>
      )}
    </section>
  );
}

// Every encoded letter, set live in the font, each over the size it was cut from.
function Glyphs({ face, encoded }) {
  const sorted = [...encoded].sort((a, b) => a.char.codePointAt(0) - b.char.codePointAt(0));
  return (
    <div className="glyphs" style={{ fontFamily: `"${face.family}", Georgia, serif` }}>
      {sorted.map((g) => (
        <div key={g.name} className={`glyphs__cell${g.constructed ? " glyphs__cell--constructed" : ""}`}>
          <span className="glyphs__char">{g.char}</span>
          <span className="glyphs__from">
            {g.constructed
              ? g.construct?.from?.length
                ? `built from ${g.construct.from.join(", ")}`
                : "built from parts"
              : sizeLabel(g.line)}
          </span>
        </div>
      ))}
    </div>
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
  const by = (face.specimen_lines || []).map((l) => l.by || "human");
  // who read most of the lines is said once; a line says so only when it differs
  const reader = [...new Set(by)].sort((a, b) => by.filter((x) => x === b).length - by.filter((x) => x === a).length)[0];
  const year = String(src.date || "").replace(/\D/g, "");
  const otf = face.fonts.find((f) => f.endsWith(".otf"));
  const ttf = face.fonts.find((f) => f.endsWith(".ttf"));

  return (
    <article className="family">
      <FontFaceStyle face={face} />
      <h1 className="family__name">{face.title || face.family}</h1>

      <dl className="colophon">
        <div className="colophon__item">
          <dt>Printed in</dt>
          <dd>
            <em>{(src.title || "").split(".")[0]}</em>, No. 9. {src.publisher}
            {year ? `, ${year}` : ""}.
          </dd>
        </div>
        <div className="colophon__item">
          <dt>Traced from</dt>
          <dd>
            {(src.leaves || []).map((l, i) => (
              <span key={l}>
                {i > 0 && ", "}
                <a className="link" href={`${src.url}/page/n${l}`}>
                  {leafPages[l] ? `page ${leafPages[l]}` : `leaf ${l}`}
                </a>
              </span>
            ))}{" "}
            of the Internet Archive&rsquo;s scan{reader ? `, read by ${READERS[reader] || reader}` : ""}.
          </dd>
        </div>
        <div className="colophon__item">
          <dt>In the font</dt>
          <dd>
            {traced} traced from the page
            {constructed > 0 ? `, ${constructed} built from traced parts` : ""}
            {alternates > 0 ? `; ${alternates} more cuts of the same letters at other sizes are in the font, unencoded` : ""}.
          </dd>
        </div>
        <div className="colophon__item">
          <dt>Version {face.version}</dt>
          <dd>
            <span className={`status status--${face.status}`}>{face.status}</span>
            {face.status === "proto" && ": traced and spaced by machine, not yet reviewed by a person."}
            {face.status === "draft" && ": cuts and spacing reviewed by a person."}
          </dd>
        </div>
        <div className="colophon__item">
          <dt>Download</dt>
          <dd>
            {otf && (
              <a className="link" href={`/fonts/${otf}`} download>
                OTF
              </a>
            )}
            {otf && ttf && ", "}
            {ttf && (
              <a className="link" href={`/fonts/${ttf}`} download>
                TTF
              </a>
            )}
            . SIL Open Font License.
          </dd>
        </div>
      </dl>

      <Tester face={face} chars={chars} />

      <section className="family__section">
        <h2 className="family__h2">Letters</h2>
        <p className="family__caption">
          {constructed > 0
            ? "Black letters are traced from the page. Gray ones the specimen never shows; they are built from traced parts. "
            : "Every letter is traced from the page. "}
          Under each is the size it was cut from.
        </p>
        <Glyphs face={face} encoded={encoded} />
      </section>

      {coveredLines.length > 0 && (
        <section className="family__section">
          <h2 className="family__h2">Printed and re-set</h2>
          <p className="family__caption">
            Above, each line as printed{year ? ` in ${year}` : ""}. Below it, the same words set in this font at the same
            cap height.
          </p>
          <div className="showings">
            {coveredLines.map((l) => (
              <figure key={`${l.leaf}-${l.band}`} className="showings__item">
                <img src={`${PROOFS}/${face.name}/proofs/${l.proof}`} alt={`${printed(l)}: the printed line over the re-set line`} loading="lazy" />
                <figcaption>
                  {sizeLabel(l.line)}
                  {(l.by || "human") !== reader ? `, read by ${READERS[l.by || "human"] || l.by}` : ""}
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}

      {lines.length > 0 && (
        <section className="family__section">
          <h2 className="family__h2">Sizes</h2>
          <p className="family__caption">
            Each size was its own set of punches or blocks, so the same design measures differently from size to size.
            Stem is the width of a vertical stroke.
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>Size</th>
                <th>Letters</th>
                <th>Cap height in the scan</th>
                <th>Stem, font units</th>
                <th>Stem to cap height</th>
              </tr>
            </thead>
            <tbody>
              {lines.map(([key, m]) => (
                <tr key={key}>
                  <td>{sizeLabel(key.split(":")[1])}</td>
                  <td>{m.glyphs ? m.glyphs.length : m.n_caps}</td>
                  <td>{Math.round(m.cap_height_px)} px</td>
                  <td>{m.stem_units ?? "n/a"}</td>
                  <td>{m.stem_units ? `${((m.stem_units / face.metrics.cap_height) * 100).toFixed(1)}%` : "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {face.arrow_attempts && face.arrow_attempts.length > 0 && (
        <section className="family__section">
          <h2 className="family__h2">Scan against trace</h2>
          <p className="family__caption">
            Gray is the scan. Cyan is potrace, the trace that made the font. Magenta is Arrow, Quiver&rsquo;s model.
            Black where all agree. Arrow was shown the R twice and both times drew a picture of it rather than its
            edge.
          </p>
          <div className="research">
            <img
              className="research__overlay"
              src={`${PROOFS}/${face.name}/proofs/R__overlay.png`}
              alt="Overlay of scan, potrace and Arrow traces of the R"
            />
            <table className="table">
              <thead>
                <tr>
                  <th>Trace</th>
                  <th>Input</th>
                  <th>Overlap with scan</th>
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
                    <td>n/a</td>
                    <td>{rGlyph.diff.potrace_contours}</td>
                  </tr>
                )}
                {face.arrow_attempts.map((a) => (
                  <tr key={a.task_id}>
                    <td>
                      {a.model}, attempt {a.attempt}{" "}
                      <a className="link" href={`${PROOFS}/${face.name}/${a.kept_as}`}>svg</a>
                    </td>
                    <td>
                      <a className="link" href={`${PROOFS}/${face.name}/${a.input}`}>
                        {a.input.split("/").pop()}
                      </a>
                    </td>
                    <td>{a.iou_scan != null ? a.iou_scan.toFixed(3) : "n/a"}</td>
                    <td>{a.best_region_iou_scan != null ? a.best_region_iou_scan.toFixed(3) : "n/a"}</td>
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

function FamilyPage({ name }) {
  const { face, error } = useFace(name);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [name]);
  return (
    <div className="page">
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
        {route.face ? (
          <a className="topbar__link" href="#/">
            All faces
          </a>
        ) : (
          <input
            className="field topbar__search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search faces"
            spellCheck={false}
            aria-label="Search faces"
          />
        )}
        <a className="topbar__link topbar__link--end" href={REPO} target="_blank" rel="noreferrer">
          GitHub
        </a>
      </header>
      {error && <p className="app__error">Could not load the index: {error}</p>}
      {route.face ? (
        <FamilyPage name={route.face} />
      ) : index ? (
        <Index index={index} query={query} />
      ) : (
        !error && <p className="app__loading">Loading…</p>
      )}
    </div>
  );
}

export default App;
