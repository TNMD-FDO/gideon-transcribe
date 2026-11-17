# PDF for the Preservation copy: tried, and set aside

Read and run on 17 November 2026. The Preservation copy (Phase 14 chapter 1)
was to hold PDFs. The app writes Word and no PDF, so a PDF maker was chosen,
built and run against real exports the same day, and the maintainer then
changed the choice to Word ("switch it to export as word"). No PDF maker is in
the app. This note keeps what was learned, for the next time PDF is asked for.
Every fact carries the address it was read from, or says that it was observed
on the trial.

## What was tried

LibreOffice Writer, in its no-GUI packages, installed from Debian 13 beside
the app's own Word writer, turning the Word exports into PDF/A-2b.

Why this and not the others:

- **A second set of layouts written with a PDF library** would mean every
  export (transcript, summary, chat, case chat, chronology, memo, comparison)
  laid out twice and kept in step for ever.
- **Gotenberg**, an upstream image that wraps LibreOffice behind an HTTP
  service, would be one more container on a server shared with another
  project, for a job a worker can do by running one command. Its
  LibreOffice-only image at tag 8.40 is about 434 MB to pull for amd64
  (https://hub.docker.com/v2/repositories/gotenberg/gotenberg/tags?page_size=5&name=8).
  Nothing else about it was read.

## LibreOffice, as Debian 13 carries it

- **Licence.** "LibreOffice is made available subject to the terms of the
  Mozilla Public License v2.0". https://www.libreoffice.org/about-us/licenses/
- **Version.** Debian 13 (trixie) carries `libreoffice-writer-nogui`
  4:25.2.3-2+deb13u9. https://packages.debian.org/trixie/libreoffice-writer-nogui
- **No GUI, no Java.** `libreoffice-core-nogui` is "architecture-dependent core
  files of LibreOffice without GUI support for server-based or commandline
  usage"; its dependencies name no X11, GTK or Qt library and no Java runtime.
  https://packages.debian.org/trixie/libreoffice-core-nogui
- **It does not look for updates.** Debian builds it with
  `--disable-online-update` among its default configure flags.
  https://sources.debian.org/data/main/libr/libreoffice/4:25.2.3-2+deb13u9/debian/rules
  (the first 100,000 characters of the file were read).
- **Running it.** `--headless`, `--convert-to` with `--outdir` and many files
  in one start, `--norestore`, and `-env:UserInstallation=file:///...` for a
  profile of its own.
  https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html
- **The archival PDF.** The filter option
  `'pdf:writer_pdf_Export:{"SelectPdfVersion":{"type":"long","value":"2"}}'`
  asks for PDF/A-2b (0 is PDF 1.7, 1 is PDF/A-1b, 3 is PDF/A-3b).
  https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html
- **Typefaces.** Debian's `fonts-crosextra-carlito` is a "sans-serif font
  metric-compatible with Calibri font".
  https://packages.debian.org/trixie/fonts-crosextra-carlito
  No free face with Consolas's widths was found.
- **Cutting the network in a build.** `RUN --network=none` is "Run with no
  network access", among the `RUN` options from Dockerfile version 1.3.
  https://docs.docker.com/reference/dockerfile/

## What the trial showed (observed, 17 November 2026)

A throwaway image on a workstation, Docker Engine 29.9.2: the app image's
Debian by digest, with `libreoffice-writer-nogui`, `fontconfig` and
`fonts-crosextra-carlito` added, and a fontconfig file mapping Calibri to
Carlito and Consolas to DejaVu Sans Mono. The 24 Word documents of the local
demo case's copy were converted by the command above.

It works:

- apt took 114 MB of archives and 368 MB of disk for the three packages and
  what they pull in.
- A conversion under `RUN --network=none` at build made a PDF/A (the file's
  own mark reads `<pdfaid:part>2</pdfaid:part>`).
- Run as an account with no entry in the container (`--user 12345:12345`),
  with no network and `HOME` set to a temporary folder: 24 of 24 documents in
  about 11 seconds, three starts of eight at about 4 seconds each. Nothing
  was left in the temporary folder.
- A four-page transcript of 40 KB as Word came to about 110 KB as PDF/A, with
  Carlito and DejaVu Sans Mono inside the file. The 24 documents were 1.0 MB
  as Word and 2.7 MB as PDF.

It does not lay a page out as Word does. Three differences, found by laying
each PDF beside the one Word itself made from the same file:

1. **Tables in equal columns.** The exports set each cell's width (`w:tcW`)
   and leave the table's list of columns (`w:tblGrid`) at even shares. Word
   lays out by the cells, LibreOffice by the list. Mended in the trial by
   writing the cells' widths into the list before converting; the page counts
   then matched Word's for every document.
2. **Line numbers on the cover.** A Transcript numbers the lines of its talk
   by a setting on that one section (`w:lnNumType`). LibreOffice numbers a
   whole document or none, so the cover's nine lines were counted and the
   talk began at 10. Mended in the trial by marking every paragraph outside
   the numbered section `w:suppressLineNumbers`.
3. **The talk's lines break differently.** With 1 and 2 mended, the words on
   a transcript's pages still differed from Word's: lines that fit on one
   line in Consolas wrapped in DejaVu Sans Mono, which is wider, so text moved
   to the next page and every line number after the first such line moved
   with it. Not mendable without a free face of Consolas's widths.

Smaller things seen: a file name in a narrow table cell breaks at a different
place; a bullet is drawn from a different face.

## Why it was set aside

A Transcript is cited by page and line, and the Word export is what people
have cited from. A PDF whose line numbers disagree with it is worse than no
PDF. The maintainer chose Word documents for the copy.

## If PDF is asked for again

- The mechanics are settled above and need no new research: the packages, the
  command, the filter, the profile, the build's proof.
- The line numbers are the whole question. Either the Word Transcript is set
  in a free fixed-width face as well (DejaVu Sans Mono is in the image
  already), so both number alike, which changes every Transcript export and
  the page and line of anything already cited; or the PDF carries its own
  line numbers and says on its cover that they are not the Word export's.
- The two mends (tables, cover line numbers) were written and worked; they
  are in the history of this repository at the commit before the one that
  removed them (`core/pdf_maker.py`, `for_the_maker`).
