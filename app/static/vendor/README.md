# Vendored, not fetched

The browser needs a few libraries, and they are kept here rather than fetched
from a content delivery network, because the app reaches nothing outside the
office at run time and adding a delivery network to the build's egress list to
save a few files in a repository would be a poor trade.

## tus.min.js

- tus-js-client 4.3.1, MIT.
- Taken from the published package, `dist/tus.min.js`, whose SHA-256 is
  `8cbb1b63fccc3bba0ae73ad1deb160ce046c3750851d0c3e94921ae3ef070eb8`.
- One line was removed: the comment pointing at a source map that is not
  shipped with it. Nothing else was changed.
- It is what resumable uploads are built on: an upload that loses its
  connection carries on from where it stopped rather than starting again, which
  is what a 1.8 GB body-worn camera export on an office network needs.

## maplibre-gl.js and maplibre-gl.css (Phase 12)

- MapLibre GL JS 5.24.0, BSD-3-Clause.
- Taken from the published package `maplibre-gl-5.24.0.tgz` (SHA-256
  `5cbf83c328c9d39cb24e3f2cefc9b407d69dd104ba0b41e84c0bfbb31c44e283`), its
  `dist/maplibre-gl.js` and `dist/maplibre-gl.css`.
- The source map comment at the foot of the script was removed, as for
  tus.min.js. Nothing else was changed. The kept files' SHA-256:
  - `maplibre-gl.js`: `8b2c6bfadb8cc2d720aea2816ac368e51ab75dbb81ee3fac2f8b97256ebd1585`
  - `maplibre-gl.css`: `ab1e70d59ec40465bae7e7030da2f3ccf28133fd502e62bd598eefbadfd7a732`
- It draws the Map tab: the street map from the basemap file and the cameras'
  paths over it. The last 5.x release was chosen on purpose: 6.x is a module
  for a bundler and needs WebGL 2 (`docs/research/basemap.md`).

## pmtiles.js (Phase 12)

- pmtiles 4.5.0, BSD-3-Clause.
- Taken from the published package `pmtiles-4.5.0.tgz` (SHA-256
  `23ae7c575578ad24cd579377d69c46550631da219e6f179997ec2cf3b8c937e5`), its
  `dist/pmtiles.js` (the plain-script build).
- The source map comment was removed. The kept file's SHA-256:
  - `pmtiles.js`: `ca16879182f180bd18648457701ec7106d2159944dca107fd17afc4110c79056`
- It teaches the map library to read the one basemap file by byte ranges,
  so the office's own server can serve the whole region as a single file.

## ../maps (Phase 12)

- `style-light.json` and `style-dark.json`: the Protomaps basemap style,
  generated once from `@protomaps/basemaps` 5.7.2 (BSD-3-Clause; package
  SHA-256 `2d5d41b29cdd2364f7092ad439bd9d170b4f38cbec8858cefbe84d0f98125ce6`)
  by `layers("protomaps", namedFlavor("light" | "dark"), {lang: "en"})`, with
  the glyphs and sprite addresses pointing at the folders below. The
  package itself is not kept; how the two files were made is in
  `docs/research/basemap.md`.
- `fonts/`: the three Noto Sans glyph stacks the style names (Regular,
  Medium, Italic), SIL Open Font License 1.1, from
  `protomaps/basemaps-assets` (the main branch's zip, SHA-256
  `c02634724bee074ac41f1bbccc7eecaa3268703d5c601d4c8f3ad0d6bb6378c7`,
  fetched 2026-11-02). Only the first eight ranges of each stack are kept
  (codepoints 0 to 2047: Latin, Greek and Cyrillic), two megabytes rather
  than seventy; a label outside those scripts draws no glyph.
- `sprites/`: the `v4` light and dark sprite sheets at 1x and 2x from the
  same zip, derived from the MIT-licensed tangrams/icons.
