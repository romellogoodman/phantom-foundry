import { useEffect, useMemo, useRef, useState } from "react";
import "@fontsource-variable/libre-franklin";
import "./App.scss";

// Fonts and proofs live in the foundry's Cloudflare R2 bucket (scripts/publish-assets.py fills it).
// The built site reads them from there; `npm run dev` reads public/ after scripts/sync-faces.sh.
// VITE_ASSETS_URL overrides either, e.g. to develop against the bucket.
const BUCKET = "https://pub-8fda51eedea94d8da574bbc563a37df4.r2.dev";
const ASSETS = (import.meta.env.VITE_ASSETS_URL ?? (import.meta.env.PROD ? BUCKET : "")).replace(/\/$/, "");
const PROOFS = `${ASSETS}/proofs`;
const FONTS = `${ASSETS}/fonts`;
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

const TWO_MODELS = "two vision models, DeepSeek V4.1 Flash and Qwen 3.7 Flash, where both gave the same letters";
const READERS = {
  claude: "Claude",
  "claude+ocr": "Claude, checked against the archive’s OCR",
  human: "a person",
  "deepseek-v4.1-flash+qwen3.7-flash": TWO_MODELS,
  "deepseek-v4.1-flash+qwen3.7-flash+ocr": `${TWO_MODELS}, checked against the archive’s OCR`,
};
const THIN = 10; // a strike with fewer letters than this is kept but not listed by default

// The same typeface shown in two books is two strikes. Their names differ only by the book's code.
// A heading as the OCR or a model read it can end in a stray full point.
function titleOf(f) {
  return (f.title || f.family || f.name || "").replace(/[\s.,;:]+$/, "");
}

function typefaceKey(f) {
  return (f.series || f.title || f.name).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}


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
  return { face: m ? decodeURIComponent(m[1]) : null, process: /^#\/process/.test(hash) };
}

// Each face's font is loaded once, on first sight, through the FontFace API.
const loaded = new Set();
function loadFont(family, file) {
  if (!file || loaded.has(family)) return;
  loaded.add(family);
  const ff = new FontFace(family, `url("${FONTS}/${file}")`, { display: "swap" });
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
  page: (a, b) =>
    (a.book || "").localeCompare(b.book || "") || (a.pages[0] || 9999) - (b.pages[0] || 9999) || a.name.localeCompare(b.name),
  name: (a, b) => titleOf(a).localeCompare(titleOf(b)) || a.name.localeCompare(b.name),
  glyphs: (a, b) => b.encoded - a.encoded || a.name.localeCompare(b.name),
  size: (a, b) => sizePt(b) - sizePt(a) || a.name.localeCompare(b.name),
};

// books in the order a shelf would hold them: by foundry, then year
function shelfOrder(a, b) {
  return (a?.issuer || a?.title || "").localeCompare(b?.issuer || b?.title || "") || (a?.year || 0) - (b?.year || 0);
}

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

function Card({ face, mode, custom, size, book, strikes }) {
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
        <span className="row__name">{titleOf(face)}</span>
        {face.status !== "proto" && <span className={`status status--${face.status}`}>{face.status}</span>}
        <span className="row__meta">{face.encoded} letters</span>
        <span className="row__meta">
          {book ? `${book.issuer || book.title}${book.year ? `, ${book.year}` : ""}` : ""}
          {pages.length ? `${book ? ", " : ""}page ${pages[0]}` : ""}
        </span>
        {strikes > 1 && <span className="row__meta">{strikes} strikes of this face</span>}
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

function Index({ index, query, books }) {
  const [mode, setMode] = useState("specimen");
  const [custom, setCustom] = useState(DEFAULT_TEXT);
  const [size, setSize] = useState(DEFAULT_SIZE);
  const [sort, setSort] = useState("page");
  const [filters, setFilters] = useState({ category: new Set(), lower: false, figures: false });
  const [book, setBook] = useState("");
  const [thin, setThin] = useState(false);
  const [more, setMore] = useState({ view: "", n: 120 }); // how far down the list is drawn, for the current view
  const all = useMemo(() => index.faces_list || [], [index]);
  const faces = useMemo(() => (thin ? all : all.filter((f) => f.encoded >= THIN)), [all, thin]);
  const bookOf = useMemo(() => Object.fromEntries((books || []).map((b) => [b.id, b])), [books]);
  const shelf = useMemo(() => {
    const n = {};
    for (const f of faces) n[f.book] = (n[f.book] || 0) + 1;
    return Object.keys(n)
      .map((id) => ({ id, n: n[id], ...(bookOf[id] || { title: id }) }))
      .sort((a, b) => (a.issuer || a.title).localeCompare(b.issuer || b.title) || (a.year || 0) - (b.year || 0));
  }, [faces, bookOf]);
  const strikes = useMemo(() => {
    const n = {};
    for (const f of all) n[typefaceKey(f)] = (n[typefaceKey(f)] || 0) + 1;
    return n;
  }, [all]);
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
      .filter((f) => !book || f.book === book)
      .filter((f) => filters.category.size === 0 || filters.category.has(f.category))
      .filter((f) => !filters.lower || f.lower > 0)
      .filter((f) => !filters.figures || f.figures > 0)
      .sort(
        sort === "page"
          ? (a, b) => shelfOrder(bookOf[a.book], bookOf[b.book]) || SORTS.page(a, b)
          : SORTS[sort],
      );
  }, [faces, query, filters, sort, book, bookOf]);
  const view = `${query}|${[...filters.category]}|${filters.lower}|${filters.figures}|${sort}|${book}|${thin}`;
  const limit = more.view === view ? more.n : 120;
  const changed =
    book !== "" || thin || mode !== "specimen" || custom !== DEFAULT_TEXT || size !== DEFAULT_SIZE || sort !== "page" ||
    filters.category.size > 0 || filters.lower || filters.figures;
  const reset = () => {
    setMode("specimen");
    setCustom(DEFAULT_TEXT);
    setSize(DEFAULT_SIZE);
    setSort("page");
    setFilters({ category: new Set(), lower: false, figures: false });
    setBook("");
    setThin(false);
  };
  return (
    <>
      <div className="intro">
        <p className="intro__lead">
          Phantom Foundry publishes strikes: faithful impressions of public domain type, taken from old specimen
          books and ready to be finished.
        </p>
        <p className="intro__note">
          In a type foundry a strike was the raw impression of a punch in copper, before anyone justified it into a
          working matrix. Foundries sold strikes to one another to be finished elsewhere. These are the same thing:
          one typeface as one book shows it, traced from the page and spaced by machine, with only the letters that
          page prints. Find one, see where it came from, and take it further. A letter a strike lacks appears as an
          empty box.
        </p>
        <p className="intro__note">
          None of this type is drawn by a model. Coding agents built the tools, and models read which letter is in
          each box and what a caption says. Every outline is traced from a printed page by potrace. All of it is
          public so you can check the work: the tools, the record behind each letter, and the fonts, under the SIL
          Open Font License and MIT. It is on{" "}
          <a className="link" href={REPO}>
            GitHub
          </a>
          , and <a className="link" href="#/process">how a strike is made</a> lists every book.
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
        <select className="field controls__book" value={book} onChange={(e) => setBook(e.target.value)} aria-label="Book">
          <option value="">Every book</option>
          {shelf.map((b) => (
            <option key={b.id} value={b.id}>
              {b.issuer || b.title}
              {b.year ? `, ${b.year}` : ""} ({b.n})
            </option>
          ))}
        </select>
        <select className="field controls__sort" value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Order">
          <option value="page">By book and page</option>
          <option value="name">By name</option>
          <option value="size">Largest size first</option>
          <option value="glyphs">Most letters first</option>
        </select>
      </div>
      <div className="browse">
        <div className="browse__bar">
          <Filters filters={filters} setFilters={setFilters} counts={counts} />
          {all.length > faces.length || thin ? (
            <Toggle on={thin} onClick={() => setThin((t) => !t)} count={all.filter((f) => f.encoded < THIN).length}>
              Under {THIN} letters
            </Toggle>
          ) : null}
          <span className="browse__count">
            {shown.length === faces.length ? `${faces.length} strikes` : `${shown.length} of ${faces.length} strikes`}
          </span>
          {changed && (
            <button type="button" className="toggle" onClick={reset}>
              Reset
            </button>
          )}
        </div>
        {shown.length === 0 ? (
          <p className="browse__empty">No strike matches. Clear the search or reset the filters.</p>
        ) : (
          <div className="browse__list">
            {shown.slice(0, limit).map((f) => (
              <Card key={f.name} face={f} mode={mode} custom={custom} size={size} book={bookOf[f.book]} strikes={strikes[typefaceKey(f)]} />
            ))}
            {shown.length > limit && (
              <button type="button" className="toggle browse__more" onClick={() => setMore({ view, n: limit + 240 })}>
                Show more ({shown.length - limit} to go)
              </button>
            )}
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
  const css = `@font-face{font-family:"${face.family}";src:url("${FONTS}/${file}") format("opentype");font-display:block}`;
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

const WANTED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

function Family({ face, index }) {
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
  const lacking = [...WANTED].filter((c) => !chars.has(c));
  const bookId = face.book || src.archive_id;
  const me = (index?.faces_list || []).find((f) => f.name === face.name);
  const others = me ? (index.faces_list || []).filter((f) => f.name !== face.name && typefaceKey(f) === typefaceKey(me)) : [];

  return (
    <article className="family">
      <FontFaceStyle face={face} />
      <h1 className="family__name">{titleOf(face)}</h1>

      <dl className="colophon">
        <div className="colophon__item">
          <dt>Printed in</dt>
          <dd>
            <em>{(src.title || "").split(/[.:;]/)[0].trim()}</em>
            {`${bookId === "bookoftypespecim00barnrich" ? ", No. 9" : ""}. ${src.publisher || ""}`}
            {year && !String(src.publisher || "").includes(year) ? `, ${year}` : ""}.
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
            {face.status === "proto" && ": a strike. Traced and spaced by machine, not yet reviewed by a person."}
            {face.status === "draft" && ": cuts and spacing reviewed by a person."}
          </dd>
        </div>
        <div className="colophon__item">
          <dt>Download</dt>
          <dd>
            {otf && (
              <a className="link" href={`${FONTS}/${otf}`} download>
                OTF
              </a>
            )}
            {otf && ttf && ", "}
            {ttf && (
              <a className="link" href={`${FONTS}/${ttf}`} download>
                TTF
              </a>
            )}
            . SIL Open Font License.
          </dd>
        </div>
      </dl>

      <Tester face={face} chars={chars} />

      <section className="family__section">
        <h2 className="family__h2">Take it further</h2>
        <p className="family__caption">
          A strike is a starting point. This one has {encoded.length} letters
          {lacking.length > 0 ? (
            <>
              {" "}
              and lacks <span className="family__lacking">{lacking.join(" ")}</span>
            </>
          ) : (
            ", a full alphabet and figures"
          )}
          . Its spacing is a machine&rsquo;s first guess, it has no kerning, and the print&rsquo;s roughness is still
          in the outlines. To finish it, open the font, or rebuild its source from the record:{" "}
          <a className="link" href={`${REPO}/tree/main/faces/${face.name}`}>
            faces/{face.name}
          </a>{" "}
          holds which box on which page is which letter, and <code className="family__code">foundry shelve {bookId}</code>{" "}
          then <code className="family__code">foundry build {face.name}</code> remakes every crop, outline and the UFO
          font source from the scan.
        </p>
        {others.length > 0 && (
          <p className="family__caption">
            The same face was shown in other books, and each showing is its own strike with its own letters:{" "}
            {others.map((f, i) => (
              <span key={f.name}>
                {i > 0 && ", "}
                <a className="link" href={`#/face/${encodeURIComponent(f.name)}`}>
                  {f.name} ({f.encoded} letters)
                </a>
              </span>
            ))}
            .
          </p>
        )}
      </section>

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

function FamilyPage({ name, index }) {
  const { face, error } = useFace(name);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [name]);
  return (
    <div className="page">
      {error && <p className="app__error">Could not load {name}: {error}</p>}
      {face ? <Family face={face} index={index} /> : !error && <p className="app__loading">Loading {name}…</p>}
    </div>
  );
}

// -- how it is made, and from which books ---------------------------------------

const STEPS = [
  ["Shelve", "A whole specimen book is fetched from the Internet Archive: every page as the library scanned it, and the archive\u2019s text recognition for the small print."],
  ["Catalog", "Each page is searched for lines of large type. Every letter shape on a line gets a box, and the caption beside it, or the heading over the page, says which typeface and size the line shows."],
  ["Found", "A typeface that one book shows large enough, with enough letters, becomes a strike: a folder holding its source pages and a record of where everything came from. The same typeface in another book is another strike."],
  ["Read", "Someone has to say which letter is in each box. Two small vision models read every line separately, and a line counts only when both give the same letters and the count fits the boxes. The rest wait for a stronger reader or a person. The archive\u2019s own text recognition gets about one letter in five wrong on display type, so it is only ever a cross-check."],
  ["Cut and cast", "Each labelled box is cropped from the scan, cleaned to black and white and traced into an outline with potrace."],
  ["Sort and justify", "The outlines are scaled onto one baseline and cap height, and the space beside each letter is set from the gaps measured on the printed page."],
  ["Proof", "The font is compiled, then set against the lines it came from. Checks flag a trace that strays from its scan, a letter that does not fit its line, and a letter that looks unlike the others filed under the same name, the sign of a wrong label. A strike that fails that last check badly is held back until a person has looked."],
];

function useBooks() {
  const [books, setBooks] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetch(`${PROOFS}/books.json`)
      .then((r) => r.json())
      .then((d) => !cancelled && setBooks(d.books || []))
      .catch(() => !cancelled && setBooks([]));
    return () => {
      cancelled = true;
    };
  }, []);
  return books;
}

function Process() {
  const books = useBooks();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  const given = (books || []).filter((b) => b.faces > 0);
  const waiting = (books || []).filter((b) => !b.faces);
  const row = (b) => (
    <tr key={b.id}>
      <td>
        <a className="link" href={b.url} target="_blank" rel="noreferrer">
          {b.issuer || b.title}
        </a>
        <span className="process__title">{b.issuer ? b.title : ""}</span>
      </td>
      <td>{b.year || ""}</td>
      <td>{b.leaves ? b.leaves.toLocaleString() : ""}</td>
      <td>{b.lines != null ? b.lines.toLocaleString() : ""}</td>
      <td>{b.faces || ""}</td>
    </tr>
  );
  const head = (
    <thead>
      <tr>
        <th>Book</th>
        <th>Year</th>
        <th>Pages scanned</th>
        <th>Lines of large type</th>
        <th>Strikes</th>
      </tr>
    </thead>
  );
  return (
    <div className="page process">
      <h1 className="family__name">How a strike is made</h1>
      <p className="family__caption">
        Every font here starts as ink on a page. A strike is one typeface as one book shows it, carried from the scan
        to a working font by a chain of small programs that pass plain files to one another, so each step can be
        opened, checked and run again. None of it starts from another font file, and no model draws a letter: models
        read which letter is in a box and what a caption says, and potrace traces every outline from the page.
      </p>
      <ol className="process__steps">
        {STEPS.map(([name, text]) => (
          <li key={name} className="process__step">
            <h2 className="process__name">{name}</h2>
            <p className="process__text">{text}</p>
          </li>
        ))}
      </ol>
      <section className="family__section">
        <h2 className="family__h2">What is kept</h2>
        <p className="family__caption">
          A face&rsquo;s record is small: which box on which page is which letter, who read it, the measurements and
          the log of every decision. From that record and the scanned book, the tools rebuild every crop, outline and
          font exactly. Early faces keep only the record. Once a person starts correcting a face by hand, all of it is
          kept.
        </p>
      </section>
      <section className="family__section">
        <h2 className="family__h2">The books</h2>
        <p className="family__caption">
          All of them are in the public domain and were scanned by libraries for the Internet Archive. Typeface
          designs cannot be copyrighted in the United States, though font files can, which is why the letters are
          taken from print.
        </p>
        {books === null ? (
          <p className="app__loading">Loading…</p>
        ) : (
          <>
            {given.length > 0 && (
              <table className="table process__table">
                {head}
                <tbody>{given.map(row)}</tbody>
              </table>
            )}
            {waiting.length > 0 && (
              <>
                <h3 className="process__h3">On the shelf, not yet struck</h3>
                <p className="family__caption">
                  Older books name a size &ldquo;Great Primer&rdquo; or &ldquo;Two-Line Pica&rdquo;, and the German,
                  French and Dutch ones use their own words. The tools find the large type in these books but cannot
                  yet tell which typeface each line belongs to.
                </p>
                <table className="table process__table">
                  {head}
                  <tbody>{waiting.map(row)}</tbody>
                </table>
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}

// -- app ----------------------------------------------------------------------

function App() {
  const { index, error } = useIndex();
  const books = useBooks();
  const route = useHash();
  const [query, setQuery] = useState("");
  return (
    <div className="app">
      <header className="topbar">
        <a className="topbar__brand" href="#/">
          Phantom Foundry
        </a>
        {route.face || route.process ? (
          <a className="topbar__link" href="#/">
            All strikes
          </a>
        ) : (
          <input
            className="field topbar__search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search strikes"
            spellCheck={false}
            aria-label="Search strikes"
          />
        )}
        <a className="topbar__link topbar__link--end" href="#/process">
          How it&rsquo;s made
        </a>
        <a className="topbar__link" href={REPO} target="_blank" rel="noreferrer">
          GitHub
        </a>
      </header>
      {error && <p className="app__error">Could not load the index: {error}</p>}
      {route.process ? (
        <Process />
      ) : route.face ? (
        <FamilyPage name={route.face} index={index} />
      ) : index ? (
        <Index index={index} query={query} books={books} />
      ) : (
        !error && <p className="app__loading">Loading…</p>
      )}
    </div>
  );
}

export default App;
