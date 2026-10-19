IBM Plex Sans (Regular, SemiBold) and IBM Plex Mono (Medium), woff2.
r3 (2026-10-19 03:2x ET): re-subset from the Designer's originals (drafts/fonts2-orig = /workspace/gia/studio/hifi/vendor/fonts2)
by ../qa/r3/subset_fonts.py: Basic Latin + Latin-1 in full plus every other character the corpus uses (data/ + built text);
unhinted, desubroutinised; tnum kept. Plex Mono Regular dropped (no built page loads it). A character outside the set
falls back to the system sans for that glyph only.
r4 (2026-10-19 03:5x ET, Director 03:53): Plex Sans Medium and Italic dropped; Sans 500 -> 600 everywhere; italic text is
synthesised from Regular by the browser. Remaining files unchanged from r3.
Licence: SIL Open Font License 1.1 (OFL.txt). Copyright © 2017 IBM Corp. with Reserved Font Name "Plex".
ea857492426c12aa9da95307198c72c71a1be473903ae6bb6ab63430784c10ee  vendor/fonts2/GIA-PlexMono-Medium.woff2
1cf134a30cf425d28220c7ed2c41cf218c03308ca21309a87c282c17f74361d8  vendor/fonts2/GIA-PlexSans-Regular.woff2
db76b389dccd1c04a8c8025a33c2a9232688a77569924d3ca7ac7cf5eaf362d9  vendor/fonts2/GIA-PlexSans-SemiBold.woff2
