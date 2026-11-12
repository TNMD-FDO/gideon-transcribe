# The street map: what is vendored, what the office fetches or cuts, and why these pins

Written 2026-11-02 for Phase 12 chapter 1 (`docs/spec/SPEC-PHASE-12.md`)
and ADR 0029. Every URL here was read on that day, and those of the last
three sections (the fetch, v1.232.0) on 2026-11-12.

## The pieces

| Piece | Version | Licence | Where it lives |
|---|---|---|---|
| MapLibre GL JS, the drawing library | 5.24.0 | BSD-3-Clause | `app/static/vendor/maplibre-gl.js`, `maplibre-gl.css` |
| pmtiles, the reader for one tile file by byte ranges | 4.5.0 | BSD-3-Clause | `app/static/vendor/pmtiles.js` |
| Protomaps basemaps, the style | 5.7.2 | BSD-3-Clause | generated once into `app/static/maps/style-light.json` and `style-dark.json`; the package is not shipped |
| basemaps-assets: Noto Sans glyphs | main, fetched 2026-11-02 | SIL OFL 1.1 | `app/static/maps/fonts/<stack>/<range>.pbf` |
| basemaps-assets: sprites v4 | main, fetched 2026-11-02 | MIT (tangrams/icons) | `app/static/maps/sprites/` |
| The tiles (OpenStreetMap data) | a dated Protomaps build | ODbL 1.0 | never shipped: `<app data folder>/maps/basemap.pmtiles`, fetched or placed by the office |
| go-pmtiles, the cutting tool | 1.31.2 | BSD-3-Clause | never shipped: the upstream image `protomaps/go-pmtiles`, pinned by tag and digest in the `transcribe` script and pulled when `./transcribe basemap fetch` runs |

The tarballs' and the kept files' SHA-256 are in `app/static/vendor/README.md`.

- MapLibre: https://registry.npmjs.org/maplibre-gl/-/maplibre-gl-5.24.0.tgz. The last 5.x release was chosen on purpose: 6.x (July 2026) ships as a module for a bundler and needs WebGL 2, neither of which the app's plain-script pages use; 5.x is a UMD script with a worker inlined as a blob.
- pmtiles: https://registry.npmjs.org/pmtiles/-/pmtiles-4.5.0.tgz, `dist/pmtiles.js` (the UMD build); `maplibregl.addProtocol("pmtiles", new pmtiles.Protocol().tile)` teaches the library the `pmtiles://` address.
- The style: https://registry.npmjs.org/@protomaps/basemaps/-/basemaps-5.7.2.tgz. Without a JavaScript runtime on the build machine the two styles were generated in the browser from the package's own bundle, `layers("protomaps", namedFlavor("light" | "dark"), {lang: "en"})`, 71 layers each, then saved with `glyphs` and `sprite` pointing at the vendored folders and an empty `sources`; the page adds the `protomaps` vector source pointing at the office's file at load.
- Fonts and sprites: https://github.com/protomaps/basemaps-assets/archive/refs/heads/main.zip. The styles name three stacks (Noto Sans Regular, Medium, Italic). Only the first eight ranges of each are kept (codepoints 0 to 2047: Latin, Greek, Cyrillic), two megabytes rather than seventy; a label outside those scripts draws no glyph. The `v4` sprites are the ones the 5.x styles draw with (the zip also holds `v3`).

## Cutting the region file by hand

The way for a server with no route to the builds, and the only way before v1.232.0. On a workstation with the internet:

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

## The fetch on the server (v1.232.0)

`./transcribe basemap fetch` does the cutting on the server, at an Admin's command, with the same tool in a container:

- The tool: https://github.com/protomaps/go-pmtiles/releases/tag/v1.31.2 (published 2026-07-22), as the image `protomaps/go-pmtiles:v1.31.2` on Docker Hub (https://hub.docker.com/r/protomaps/go-pmtiles/tags), index digest `sha256:06574f01f55a78f78f887bc7ebf729a5c093c0d6e17d9876300cfcb0758b59d3`, about 18 MB to pull and 80.7 MB once on a server's Docker volume. Its `Dockerfile` builds one static program onto `gcr.io/distroless/static` with the program as the entry point, so it runs under any account given with `--user`.
- What it takes, read from its source at that tag (`pmtiles/region.go`, `pmtiles/extract.go`, `main.go`): `--region` is a GeoJSON file that may be a FeatureCollection of polygons, a Feature or a bare geometry, so several rectangles go in one cut; `--dry-run` reads the build's directories and prints `Extract transferred N (overfetch 0.05) for an archive size of M` without fetching a tile; `--download-threads` defaults to 4; a build that is not there fails with `HTTP error: 404` and exit 1; and the output file's header is written last, so a cut that is interrupted does not begin with the bytes `PMTiles`. The script checks those bytes before the new file takes the old one's place.
- The builds: https://build.protomaps.com/YYYYMMDD.pmtiles, one a day, kept a week (https://docs.protomaps.com/basemaps/downloads). On 2026-11-12 the builds of the 6th to the 12th answered a read of their first bytes with 206 and the 5th with 404. There is therefore no fixed file to pin by digest: the script takes the newest build of the last eight days and records its date beside the map (`maps/basemap.json`), which the Status page shows.
- The areas: the 50 states, the District of Columbia and the five territories, each as its bounding rectangle from the Census Bureau's boundaries (the list at https://gist.github.com/a8dx/2340f9527af64f8ef8439366de981168, rounded outward to two decimals), widened by 0.1 of a degree when the region file is written. Alaska is two rectangles, split at the date line, the western one running from 172.30 east to cover Attu. The whole country is the lower 48 with the District as one rectangle (-124.77, 24.52 to -66.94, 49.39) and each of Alaska, Hawaii, Puerto Rico, the US Virgin Islands, Guam, the Northern Mariana Islands and American Samoa by its own: nine rectangles.

## The sizes, measured

From the build of 11 November 2026, at full detail (zooms 0 to 15), by reading the build's directories as a dry run does. Gigabytes here are thousands of megabytes, as the tool says them.

| Area (as one rectangle each) | Size | With zoom 14 as the finest | With zoom 13 |
|---|---|---|---|
| The whole planet, for scale | 139.4 GB | | |
| The lower 48 states and the District | 18.80 GB | 8.86 GB | 4.25 GB |
| Alaska | 1.43 GB | 0.75 GB | 0.40 GB |
| Alaska's islands past the date line | under 0.01 GB | | |
| Hawaii's main islands | 0.03 GB | | |
| Puerto Rico and the US Virgin Islands | 0.07 GB | | |
| Guam and the Northern Mariana Islands | 0.01 GB | | |
| American Samoa | under 0.01 GB | | |
| Rhode Island | 0.08 GB | | |
| Colorado | 0.52 GB | | |
| New York | 1.41 GB | | |
| California | 1.48 GB | | |
| Texas | 1.47 GB | | |

The tool's own dry run of the script's nine rectangles, with their margins, on the build of 12 November 2026: 46.3 million tiles covered, 18.4 million distinct, `transferred 21 GB ... for an archive size of 20 GB`, worked out in 40 seconds. Each zoom dropped about halves the size, and it is the finest streets that go, the ones a camera's path is read against, so the fetch offers full detail only.

## What was proven, and how

On a workstation, with the tool's Windows program of the same release (its SHA-256 checked against the release's own): a cut of Puerto Rico and Guam from a region file of two rectangles made an 80 MB file in ten seconds that `pmtiles verify` passed, with bounds running from one to the other; and the script's own functions, with that program standing in for the container, found the day's build, sized three territories at 78 MB, fetched them, placed the file and wrote its note, then on a second run offered the same again and stopped a whole-country fetch for want of room on that workstation's drive. Not proven before the release: the container itself on a server (the image's pull, the `--user` and the mount), which the first `./transcribe basemap fetch` on a server proves; a failure there leaves the map in place untouched.

Proven on a server on 2026-11-12, the day of the release: a fetch of one state by name pulled the image, ran the tool under the app's account, and put a whole 408 MB file in place with its note, the map that was there staying until then; the Status page read the note. Twenty scattered reads of 64 KB from the new file took well under a millisecond each, as from the 133 MB file before it. Two things that first day showed went into v1.233.0: a fetch closed at a question left its small region file beside the map until the next fetch, and a fetch long enough to outlast sudo's memory of the password (the whole country) would have stopped at a prompt before its last steps; the command now clears what it left half done however it ends, and keeps sudo awake while it runs.
