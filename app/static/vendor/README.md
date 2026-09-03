# Vendored, not fetched

The browser needs one library, and it is kept here rather than fetched from a
content delivery network, because the app reaches nothing outside the office at
run time and adding a delivery network to the build's egress list to save 87 KB
in a repository would be a poor trade.

## tus.min.js

- tus-js-client 4.3.1, MIT.
- Taken from the published package, `dist/tus.min.js`, whose SHA-256 is
  `8cbb1b63fccc3bba0ae73ad1deb160ce046c3750851d0c3e94921ae3ef070eb8`.
- One line was removed: the comment pointing at a source map that is not
  shipped with it. Nothing else was changed.
- It is what resumable uploads are built on: an upload that loses its
  connection carries on from where it stopped rather than starting again, which
  is what a 1.8 GB body-worn camera export on an office network needs.
