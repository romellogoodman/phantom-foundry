"""reader — two small vision models read a band; a reading counts only where they agree.

`survey` boxes the letter shapes of a line; something has to say which letter
is in each box. This is the scripted reader for a shelf of books. It sends the
numbered-box crop of a band to each model in `MODELS` through OpenRouter and
records a reading only when every model returns the same tokens and the token
count equals the box count. Bands they disagree on stay unread, for a stronger
reader or a person. Nothing here draws a letter.

Why these models, this rule and these exclusions: agent_docs/reader-bakeoff.md.

    books/<id>/readings.json   agreed readings, `by` = BY
    books/<id>/reader.jsonl    every band sent: each model's answer, agreed or not, cost
    books/.reader-cache/       raw API answers (ignored); a rerun costs nothing
"""

from __future__ import annotations

import base64
import io
import json
import re
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

from .book import BOOKS_DIR, Book
from .cut import reading_tokens
from .face import FACES_DIR, REPO_ROOT

URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS = ["deepseek/deepseek-v4.1-flash", "qwen/qwen3.7-flash"]
BY = "deepseek-v4.1-flash+qwen3.7-flash"
# DeepSeek reasons by default: ~7,500 hidden tokens and 50 s for a 30-letter line, for no gain here.
# Only enabled:false stops it on this route; effort "low"/"minimal" spend the budget and return nothing.
REASONING = {"enabled": False}
MIN_TALL_PX = 115
MAX_LONG_EDGE = 2000
CACHE = BOOKS_DIR / ".reader-cache"
# Overlapping letters: the boxes merge or split them and every model reads the word, not the boxes
# (56% of letters right even when two models agree). These series wait for a reader that can.
OVERLAPPING = re.compile(r"italic|script|cursive|inclined|oblique|slope|ronde|kursiv|backslant", re.I)

PROMPT = """You are transcribing one line ("band") cropped from a scanned 19th-century \
metal- or wood-type specimen book. A tool has drawn {n} numbered boxes on the image, one around \
each letter- or character-shape, left to right in reading order. Small numbers (1 through {n}) \
are printed just below each box — those numbers are machine-added labels for you to reference, \
not part of the printed type.

Read what is inside each box, in box order, and return exactly {n} tokens — one per box, numbered \
1 to {n} — as a JSON object: {{"tokens": ["...", "...", ...]}}.

Token rules, in order of priority:
1. Normally a box holds one printed character: a letter or a digit. The token is that character, \
exactly as printed — preserve capital vs. lowercase (a specimen line is often set in all capitals, \
or capitals over mixed case; read the actual shape, do not guess from what a real word would need). \
Read the letter shape itself, not what would make a sensible English word — specimen lines are \
often names, nonsense phrases, or fragments, not real sentences.
2. If a box holds two or more letter-shapes that are touching or fused into one connected blob \
(common in italic and script faces, and with kerning types like f, r, or T that overhang), put all \
of those letters in reading order inside square brackets as ONE token, e.g. "[fi]" for a touching f \
and i, or "[EXA]" for three touching capitals E, X, A. This is still exactly one token for that one box.
3. If a box's content is genuinely illegible (badly inked, damaged type, totally ambiguous), use "?".
4. If a box is not a letter at all — a printer's rule, an ornament, a speck of dirt, an empty or \
blank box — use "~".

Do not merge, split, skip, or reorder boxes: the output array's length must be exactly {n}, matching \
the {n} numbered boxes left to right. Do not add commentary, markdown, or code fences — respond with \
the JSON object only."""


def api_key() -> str:
    env = REPO_ROOT / ".env"
    for line in env.read_text().splitlines() if env.exists() else []:
        if line.startswith("OPENROUTER_API_KEY="):
            key = line.split("=", 1)[1].strip().strip("'\"")
            if key:
                return key
    raise RuntimeError("OPENROUTER_API_KEY is not set in .env")


def _image(path: Path) -> str:
    im = Image.open(path).convert("RGB")
    if max(im.size) > MAX_LONG_EDGE:
        k = MAX_LONG_EDGE / max(im.size)
        im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def parse_tokens(content: str | None) -> list[str] | None:
    """The `tokens` array of a model's answer, or None when there is no usable one."""
    m = re.search(r"\{.*\}", content or "", re.S)
    try:
        tokens = json.loads(m.group())["tokens"] if m else None
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return [str(t) for t in tokens] if isinstance(tokens, list) else None


def ask(model: str, book: Book, leaf: int, band: dict, key: str) -> dict:
    """One model's answer for one band: {'tokens', 'cost', 'cached'} (tokens None on failure)."""
    cp = CACHE / model.replace("/", "_") / "off" / book.archive_id / f"leaf{leaf:04d}_b{band['band']}.json"
    if cp.exists():
        raw, cached = json.loads(cp.read_text()), True
    else:
        payload = {"model": model, "temperature": 0, "reasoning": REASONING,
                   "messages": [{"role": "user", "content": [
                       {"type": "text", "text": PROMPT.format(n=band["n"])},
                       {"type": "image_url", "image_url": {"url": _image(book.dir / band["crop"])}}]}]}
        raw, cached = None, False
        for attempt in range(4):
            try:
                r = requests.post(URL, json=payload, timeout=90, headers={"Authorization": f"Bearer {key}"})
                if r.status_code == 200:
                    body = r.json()
                    # a provider's filter can misfire: HTTP 200 with a per-choice error and no content
                    if (body.get("choices") or [{}])[0].get("message", {}).get("content"):
                        raw = body
                        break
            except (requests.RequestException, ValueError):
                pass
            time.sleep(2.0 * 2 ** attempt)
        if raw is None:
            return {"tokens": None, "cost": 0.0, "cached": False}
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps(raw))
    content = ((raw.get("choices") or [{}])[0].get("message") or {}).get("content")
    return {"tokens": parse_tokens(content), "cost": (raw.get("usage") or {}).get("cost") or 0.0, "cached": cached}


def agree(answers: list[list[str] | None], n: int) -> list[str] | None:
    """The tokens, if every model gave the same ones and they fit the boxes."""
    first = answers[0]
    if first and len(first) == n and all(a == first for a in answers[1:]):
        return first
    return None


def spaced(tokens: list[str], letters: list[dict]) -> str:
    """One token per box runs the words together, and `justify` measures printed
    letter gaps between word breaks. Put the breaks back from the boxes: a gap
    well over the line's median is a word space (exact on 95% of BB&S lines)."""
    gaps = [letters[i + 1]["x"] - (letters[i]["x"] + letters[i]["w"]) for i in range(len(letters) - 1)]
    if len(gaps) != len(tokens) - 1 or not gaps:
        return " ".join(tokens)
    floor = max(1.8 * max(statistics.median(gaps), 1), 0.15 * statistics.median(l["h"] for l in letters))
    out = tokens[0]
    for tok, gap in zip(tokens[1:], gaps):
        out += (" " if gap > floor else "") + tok
    return out


def unread_bands(book: Book) -> list[tuple[int, dict]]:
    """Every band of a face founded from this book that has no reading yet,
    leaving out series whose letters overlap."""
    import yaml
    cat, have = book.catalog(), book.readings()
    out, seen = [], set()
    for fy in sorted(FACES_DIR.glob("*/face.yaml")):
        d = yaml.safe_load(fy.read_text()) or {}
        if d.get("book") != book.archive_id or OVERLAPPING.search(d.get("series") or ""):
            continue
        for leaf in d["source"]["leaves"]:
            for b in cat["leaves"].get(str(leaf), {}).get("bands", []):
                k = (leaf, b["band"])
                if (b.get("series") == d["series"] and b["tall_px"] >= MIN_TALL_PX and b["n"] >= 2 and b.get("crop")
                        and f"{leaf}:{b['band']}" not in have and k not in seen):
                    seen.add(k)
                    out.append((leaf, b))
    return out


def read_book(book: Book, budget: float = 5.0, concurrency: int = 32) -> dict:
    """Read every unread band of the book's faces; record what the models agree on."""
    from .book import import_readings
    todo = unread_bands(book)
    key = api_key() if todo else ""
    spent, lock = [0.0], threading.Lock()

    def one(job):
        leaf, band = job
        if spent[0] >= budget:
            return None
        answers = [ask(m, book, leaf, band, key) for m in MODELS]
        with lock:
            spent[0] += sum(a["cost"] for a in answers if not a["cached"])
        return leaf, band, answers

    with ThreadPoolExecutor(concurrency) as pool:
        results = [r for r in pool.map(one, todo) if r]
    agreed, log = [], []
    for leaf, band, answers in results:
        tokens = agree([a["tokens"] for a in answers], band["n"])
        log.append({"leaf": leaf, "band": band["band"], "boxes": band["n"], "agreed": tokens is not None,
                    "readings": {m: ("".join(a["tokens"]) if a["tokens"] else None) for m, a in zip(MODELS, answers)},
                    "cost": round(sum(a["cost"] for a in answers), 6)})
        if tokens:
            letters = next(x for x in json.loads(book.survey_path(leaf).read_text())["lines"]
                           if x["band"] == band["band"])["letters"]
            agreed.append({"leaf": leaf, "band": band["band"], "text": spaced(tokens, letters), "by": BY,
                           "note": "word breaks put back from the gaps between boxes"})
    if log:
        with (book.dir / "reader.jsonl").open("a") as f:
            for rec in sorted(log, key=lambda r: (r["leaf"], r["band"])):
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if agreed:
        tmp = book.dir / ".agreed.json"
        tmp.write_text(json.dumps(agreed, ensure_ascii=False))
        import_readings(book, tmp, by=BY)
        tmp.unlink()
    return {"book": book.archive_id, "bands": len(todo), "read": len(results), "agreed": len(agreed),
            "open": len(results) - len(agreed), "spent": round(spent[0], 4)}
