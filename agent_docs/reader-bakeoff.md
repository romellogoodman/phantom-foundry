# Who reads the letters: the reader bake-off (2026-09-21)

`survey` boxes the letter shapes in a line of display type; something then has
to say which letter is in each box. For the first hundred faces that was Claude
(Sonnet subagents, 30 crops a job, checked against the archive's OCR). Scaling
to a shelf of books needed a reader that is a script, not a session. This is
what we measured before choosing one. Like the Arrow finding, it is a result
about what a model does with a printed letter, and it belongs to the research.

## The test

878 lines from BB&S Specimen Book No. 9 whose readings had been accepted (872
read by Claude, 46 of them re-read, all scored against OCR and box counts). Each
model got the numbered-box crop and the box count, and returned one token per
box: a character, `[fi]` for letters sharing a box, `?`, or `~` for not a letter.
Four lines marked "not type" for a policy reason (columns under the size floor)
were left out: no reader could infer that from the picture.

| Reader | Letters right | Whole lines right | Cost per 13,000 lines |
|---|---|---|---|
| archive.org OCR | 77.6% | 60.7% | free |
| `google/gemini-2.5-flash-lite` | 89.7% | 79.7% | $4.66 |
| `deepseek/deepseek-v4.1-flash`, reasoning off | 91.9% | 83.8% | about $2 |
| `qwen/qwen3.7-flash` | 93.1% | 81.8% | $0.49 |

DeepSeek reasons by default: one 30-letter line took 7,543 hidden tokens, 52
seconds and $0.0087. On OpenRouter only `"reasoning": {"enabled": false}` stops
it; `effort: minimal` and `low` spend the whole token budget thinking and return
no content. With reasoning off the same line takes 2–3 seconds and $0.0002, and
20 of 20 smoke-test lines were exact, so the thinking bought nothing here.

## Agreement is the instrument

No single cheap model is good enough. They make different mistakes, so two
agreeing is a strong signal. With the gate `label --auto` already applies (token
count must equal box count), italics left out:

| Rule | Lines accepted | Letters right | Whole lines right |
|---|---|---|---|
| DeepSeek alone | 97.6% | 96.4% | 91.7% |
| **DeepSeek = Qwen** (the rule in use) | 88.6% | 99.3% | 97.5% |
| any two of three agree | 92.9% | 99.2% | 96.8% |
| all three agree | 82.5% | 99.6% | 98.7% |

By category, lines where DeepSeek and Qwen agree: serif, sans and wood 99%,
blackletter 98%, display 97%.

## Where it fails

- **Italics and scripts.** 56% of letters right even when two models agree.
  Italic letters overlap, the survey's boxes merge or split them, and the models
  read the *word* rather than the *boxes*, so labels slide out of step. Series
  whose names say italic, script, cursive, inclined or oblique are not read by
  this reader at all. That is a boxing problem before it is a reading problem.
- **Boxes, not letters.** Most agreed-but-wrong lines are lines where two
  touching letters share a box (`WREATH OF [RE]D ROSES`) or a second column the
  reading protocol marks `~`. The count gate rejects most of these.
- **Lowercase is dropped more than capitals.** 94% of all-caps lines pass the
  rule but only 82% of mixed-case lines; 40% of the lines that fail do so on
  count, not on letters (dots of i and j, ligatures, touching pairs). A face can
  come out caps-only because its mixed-case lines were the ones left unread.

## What is recorded

A reading's `by` names its readers (`deepseek-v4.1-flash+qwen3.7-flash`); lines
the two disagree on stay unread and are listed per book for a stronger reader or
a person. Nothing here draws a letter: every outline is traced from the scan by
potrace. Scripts, caches and raw answers of the bake-off are kept with the
session's working files; the numbers above are from `results.md` and the
agreement scoring run on the cached answers.
