---
target: dashboard.html
total_score: 15
max_score: 36
na_heuristics: 5
p0_count: 1
p1_count: 3
target_identity: "file:C:\\Users\\Bryan\\Documents\\intel-gia\\dashboard.html"
target_fingerprint: "sha256:4792098b65c24f46b967c762170e0d5a466c843a013f5d07cd3af0e03f0be765"
target_path: "C:\\Users\\Bryan\\Documents\\intel-gia\\dashboard.html"
timestamp: 2026-10-19T21-25-36Z
slug: dashboard-html
---
Method: dual-agent (A: design review · B: detector + browser evidence), isolated and parallel.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Map load states are honest; nothing marks reading position across a 5,620px page. |
| 2 | Match System / Real World | 2 | "Hot zone", "trace", "path to today", bare likely/possible/speculative pills — all undefined on the page. |
| 3 | User Control and Freedom | 1 | No filter, sort, collapse or jump. Only state mechanism is CSS :target, phone-only. |
| 4 | Consistency and Standards | 2 | Four corner radii; two icon systems for one marker taxonomy; board ranks by severity while connect/stories rank by date. |
| 5 | Error Prevention | n/a | Static read-only publication: no input, no destructive action. |
| 6 | Recognition Rather Than Recall | 1 | Map legend defines 25 symbols, then scrolls away; board glyphs carry only title attributes. |
| 7 | Flexibility and Efficiency | 1 | 136 tab stops, no shortcuts, no skip link, no exposed anchors — on a page read daily. |
| 8 | Aesthetic and Minimalist Design | 2 | Seven h2 at identical 22px; two of seven sections empty; storylines consume 38% of phone height. |
| 9 | Error Recovery | 2 | Map failure copy is plain but offers no retry; empty sections give no next step. |
| 10 | Help and Documentation | 1 | No explanation of what GIA is, what severity means, or what the confidence pills rate. |
| **Total** | | **15/36** | **Poor (42%)** |

Heuristic 5 is n/a (static publication). Applicable maximum 36.

## Design Specificity Verdict

Authored in the map layer and the severity system; category-interchangeable everywhere the actual intelligence lives. The phone map solver and the severity meter are genuinely product-specific. The three sections carrying the day's intelligence are same-size dark cards that would serve a changelog or an RSS reader unchanged.

The positioning is literally absent from the artifact: the words confidence, judgment and analysis occur zero times in the built page.

### Deterministic scan

47 CLI findings, of which 46 are false positives — a 98% false-positive rate.

- low-contrast x33: the detector paired screen-media text colours with the print-media background. Measured on screen across 341 text nodes: 0 failures; white never occurs as an effective background on screen. 25 are outright false; 8 are real but print-only.
- cramped-padding x11: false. Visible list items with border-top and padding under 8px: 0. The wmap finding is geometrically true but its nearest text sits 62.6px from the frame.
- flat-type-hierarchy x1: false. Detector reported body 112px / h2 126px / h3 133px, off by roughly 8x. Measured: h3 to h2 = 1.57:1, h2 to h1 = 1.27:1, both above the 1.25 target.
- repeating-stripes-gradient x1: false. The rule exists in CSS; zero elements carry the class. Nothing striped is ever painted.
- shape-assembled-illustration x1: real, but mobile-only (the 390px map placeholder).

The in-page detector found one rule the CLI missed entirely: line-length, 6 paragraphs at roughly 155 characters.

## What's Working

1. The severity meter is a real instrument: four bars, the word, and a Carbon glyph on critical only — one value encoded three independent ways, colourblind- and screen-reader-safe.
2. The phone map is authored, not responsive-by-default: a separate regional crop with collision-free label placement and leader lines. The 390px rendering is more legible than the 1280px one.
3. Causes and effects are split into labelled directional groups rather than merged into one misleading sequence.
4. The screen contrast floor genuinely holds: every text sample measures above 5.0:1 against its real computed ancestor background.

## Priority Issues

### [P0] The dashboard never shows a judgment

edition_row() renders title, meta and summary, and stops. The analysis object and its confidence label are never emitted. The words confidence, judgment and analysis appear zero times in the built page. The 10 confidence pills present sit only on causal links, with nothing saying what they rate. The product's stated differentiator renders on trace pages nobody lands on, and not on the page everybody lands on.

Fix: give edition_row() the analysis treatment card() already has — summary as reported fact, then a distinct .an block carrying the .conf pill and the judgment text. Reuse the existing vocabulary.

Command: /impeccable clarify

### [P1] Three sections answer "what is urgent today" with two different orderings

board() ranks by severity rank then story count. connect() and sec-stories both sort by date descending. Today a routine patrol log leads both lists while two critical items land fifth and sixth. Only three severity meters exist on the whole page, all in the board.

Fix: one ordering everywhere — max severity of any hot zone listing the story, then date. Put meter() on every story row and every connect card header.

Command: /impeccable shape

### [P1] The day's news is the last thing on the page

Section tops: map 159, board 933, markets 2124 (empty), connect 2229, storylines 3924, calendar 7897 (empty), stories 8002 of a 10,426px phone page. The first story link is tab stop 129 of 136. Two empty sections sit between the reader and the content at full h2 weight.

Fix: move sec-stories directly under sec-board. Add a skip link and a section nav. Collapse empty sections to one quiet line.

Command: /impeccable layout

### [P1] Print contrast: 8 real failures, both colours introduced in this session

.cxlab x7 — the "What led to this" labels, 2.06:1 on white at 11px. Root cause: the path token is the only colour with no print override, while every sibling token has one.
.qrow x1 — the "Nothing filed this edition" line, 3.30:1 on white at 13px. Passes on screen at 5.41:1; no print remap exists.

Both were added during the 2026-10-19 redesign. Print is not a priority for the owner, but accessibility is recorded as a hard constraint and the print styles worked before this change.

Fix: add print overrides for the path token and the qrow colour.

Command: /impeccable audit

### [P2] Phone drops severity for two thirds of hot zones, in 24px targets

phonemap.py renders unmapped zones as a plain comma-separated run with no severity word and no severity colour, while numbered entries get 44px rows and their severity. Today that run contains a critical zone and four high zones rendered identically to watch zones. Eleven links measure 24px against the stated 48px floor.

Fix: give those entries the severity word in its token colour, order by severity rank, 44px rows.

Command: /impeccable adapt

## Persona Red Flags

Alex (power user): scrolls 4,521px before a story summary; no shortcuts, no skip link, no exposed anchors despite every section carrying an id; the map is one enormous tab stop wrapping a 1222x507 SVG; no severity filter; reads sec-stories first and forms the wrong picture of the day.

Sam (accessibility-dependent): no skip link and no nav element — 129 tabs to the first story; board markers are title attributes on non-interactive spans, so the event-type dimension is unavailable; the hero map is a single link whose entire content is one 180-character title covering 18 zones; the focus ring is correct but drawn around the page's largest block, off-screen at 200% zoom; an h3 styled down to 12px gray pollutes the heading list; 11 phone targets at 24px.

The daily operator: there is no delta — nothing shows what changed since yesterday, though storyline cards carry last-entry and severity data attributes in the DOM and render neither; the same title is re-rendered up to five times per edition at four different truncation lengths; the board's severity ranking is invisible because nothing says it ranked.

The cold visitor: nothing says what this is; the map alarms without orienting (three critical labels on three continents plus 25 legend symbols); the confidence pills are undecodable because the page never uses the word confidence; two empty sections within the first 2,200px read as half-built; hot zone, trace, path and "Not pinned" are undefined.

## Minor Observations

- Line length: six story paragraphs run roughly 155 characters against a target under 80. Both assessments found this independently.
- h3 renders at 14px/600 — the same size as body text, separated by weight alone.
- One marker taxonomy, two visual systems: the legend draws coloured Carbon SVG shapes; the board renders the same types as uncoloured Unicode glyphs.
- Four corner radii coexist (8px, 10px, 2px, 0px) — two un-merged CSS vocabularies.
- Confidence pills borrow severity's amber family, so two unrelated scales share hues.
- _sec() accepts a note parameter it never interpolates; two call sites still compute and pass strings that are discarded. Dead code left by the descriptor removal — a silent-discard class.
- "Bryan has not approved pinning the strait" leaks the operator's name to a public audience.
- Browser surfaces (selection, caret, scrollbar) are themed from the palette — the cheapest signal a page was built rather than assembled.
