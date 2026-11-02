# The street map: what is vendored, what the office cuts, and why these pins

Written 2026-11-02 for Phase 12 chapter 1 (`docs/spec/SPEC-PHASE-12.md`)
and ADR 0029. Every URL here was read on that day.

## The pieces

| Piece | Version | Licence | Where it lives |
|---|---|---|---|
| MapLibre GL JS, the drawing library | 5.24.0 | BSD-3-Clause | `app/static/vendor/maplibre-gl.js`, `maplibre-gl.css` |
| pmtiles, the reader for one tile file by byte ranges | 4.5.0 | BSD-3-Clause | `app/static/vendor/pmtiles.js` |
| Protomaps basemaps, the style | 5.7.2 | BSD-3-Clause | generated once into `app/static/maps/style-light.json` and `style-dark.json`; the package is not shipped |
| basemaps-assets: Noto Sans glyphs | main, fetched 2026-11-02 | SIL OFL 1.1 | `app/static/maps/fonts/<stack>/<range>.pbf` |
| basemaps-assets: sprites v4 | main, fetched 2026-11-02 | MIT (tangrams/icons) | `app/static/maps/sprites/` |
| The region's tiles (OpenStreetMap data) | a dated Protomaps build | ODbL 1.0 | never shipped: `<app data folder>/maps/basemap.pmtiles`, placed by the office |

The tarballs' and the kept files' SHA-256 are in `app/static/vendor/README.md`.

- MapLibre: https://registry.npmjs.org/maplibre-gl/-/maplibre-gl-5.24.0.tgz. The last 5.x release was chosen on purpose: 6.x (July 2026) ships as a module for a bundler and needs WebGL 2, neither of which the app's plain-script pages use; 5.x is a UMD script with a worker inlined as a blob.
- pmtiles: https://registry.npmjs.org/pmtiles/-/pmtiles-4.5.0.tgz, `dist/pmtiles.js` (the UMD build); `maplibregl.addProtocol("pmtiles", new pmtiles.Protocol().tile)` teaches the library the `pmtiles://` address.
- The style: https://registry.npmjs.org/@protomaps/basemaps/-/basemaps-5.7.2.tgz. Without a JavaScript runtime on the build machine the two styles were generated in the browser from the package's own bundle, `layers("protomaps", namedFlavor("light" | "dark"), {lang: "en"})`, 71 layers each, then saved with `glyphs` and `sprite` pointing at the vendored folders and an empty `sources`; the page adds the `protomaps` vector source pointing at the office's file at load.
- Fonts and sprites: https://github.com/protomaps/basemaps-assets/archive/refs/heads/main.zip. The styles name three stacks (Noto Sans Regular, Medium, Italic). Only the first eight ranges of each are kept (codepoints 0 to 2047: Latin, Greek, Cyrillic), two megabytes rather than seventy; a label outside those scripts draws no glyph. The `v4` sprites are the ones the 5.x styles draw with (the zip also holds `v3`).

## Cutting the region file

On a workstation with the internet (never the server):

1. Fetch the `pmtiles` command-line tool from https://github.com/protomaps/go-pmtiles/releases (one binary per platform).
2. Find the bounding box of the office's region at http://bboxfinder.com/ (draw a rectangle; copy the "MIN_LON,MIN_LAT,MAX_LON,MAX_LAT" line).
3. Pick a build at https://maps.protomaps.com/builds/ (one a day; any recent one).
4. Cut:

```bash
pmtiles extract https://build.protomaps.com/YYYYMMDD.pmtiles basemap.pmtiles --bbox=MIN_LON,MIN_LAT,MAX_LON,MAX_LAT
```

The tool reads only the ranges it needs from the build, so the download is the size of the region, not the planet. A county at full zoom is tens to a few hundred megabytes; `--maxzoom=14` cuts the size several-fold at the cost of the finest streets. Then on the server:

```bash
./transcribe basemap /path/to/basemap.pmtiles
```

The attribution the map shows is "© OpenStreetMap contributors · Protomaps", which the ODbL and Protomaps ask for.

## Serving

Caddy serves the one file from a third read-only root (`/maps/*`, `root * /srv/maps`, mounted from `${APP_DATA_DIR}/maps`), behind `forward_auth app:8000 { uri /maps-auth }`, with `Cache-Control: private, max-age=604800`. The route sits outside the `encode` block so byte ranges stay native; `caddy/check-ranges.sh` proves a 206 on it. The library reads the file's header once and then small ranges per tile as the map moves; a week's private cache keeps a pan from reading the same tiles again.
