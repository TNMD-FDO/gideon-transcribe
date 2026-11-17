# The PDF maker: facts behind the choice

Read on 17 November 2026 for the Preservation copy, whose documents are PDFs.
The app made no PDF before this. Every fact below carries the address it was
read from. What could only be learned by running the tool is listed at the
end as not yet known, and is filled in when the first build measures it.

## The choice

LibreOffice Writer, in its no-GUI packages, installed from Debian 13 into the
app image, turning the Word files the app already writes into PDFs. No new
image and no new container.

Why this and not the others:

- **A second set of layouts written with a PDF library** would mean every
  export (transcript, summary, chat, case chat, chronology, memo, comparison)
  laid out twice and kept in step for ever. Converting the Word file keeps one
  layout.
- **Gotenberg**, an upstream image that wraps LibreOffice behind an HTTP
  service, would be one more container to pin, start, watch and give a network
  to, on a server shared with another project, for a job a worker can do by
  running one command. Its LibreOffice-only image at tag 8.40 is about 434 MB
  to pull for amd64
  (https://hub.docker.com/v2/repositories/gotenberg/gotenberg/tags?page_size=5&name=8,
  read 17 November 2026). Nothing else about it was read; it was set aside on
  shape, not on a fault.

## LibreOffice, as Debian 13 carries it

- **Licence.** "LibreOffice is made available subject to the terms of the
  Mozilla Public License v2.0". https://www.libreoffice.org/about-us/licenses/
- **Version.** Debian 13 (trixie) carries `libreoffice-writer-nogui`
  4:25.2.3-2+deb13u9, "office productivity suite -- word processor (no GUI
  variant)". https://packages.debian.org/trixie/libreoffice-writer-nogui
  The app image's base is Debian 13 by digest, and its apt versions are
  unpinned for the reason its Dockerfile gives; the same holds here, with the
  exact version of each Release recorded in `THIRD_PARTY_LICENSES.md`.
- **No GUI, no Java.** `libreoffice-core-nogui` is "architecture-dependent core
  files of LibreOffice without GUI support for server-based or commandline
  usage"; its dependencies name no X11, GTK or Qt library and no Java runtime.
  https://packages.debian.org/trixie/libreoffice-core-nogui
- **Size on disk**, as Debian's pages give it for amd64: the Writer package
  30.2 MB installed, the core 107.3 MB, the common files 48.6 MB. The
  libraries they pull in come on top, so the image grows by more than the 186
  MB these three add; the true figure is the build's to measure.
  https://packages.debian.org/trixie/libreoffice-writer-nogui
  https://packages.debian.org/trixie/libreoffice-core-nogui
  https://packages.debian.org/trixie/libreoffice-common
- **It does not look for updates.** Debian builds it with
  `--disable-online-update` among its default configure flags.
  https://sources.debian.org/data/main/libr/libreoffice/4:25.2.3-2+deb13u9/debian/rules
  (the first 100,000 characters of the file were read; the flag is in the
  `CONFIGURE_FLAGS` block). The build must still prove it at run time: a
  conversion with the container's network cut must succeed.

## Running it

- `--headless` "allows using the application without user interface".
  `--convert-to OutputFileExtension [:OutputFilterName
  [:OutputFilterParams[,param]]] [--outdir output_dir]`, with the page's own
  example `--convert-to pdf:writer_pdf_Export --outdir /home/user *.doc`, so
  one start converts many files. `--norestore` "disables restart and file
  recovery after a system crash". `-env:UserInstallation=file:///...` sets "a
  non-default user profile path", which is how two conversions at once are
  kept from sharing a profile.
  https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html
- **The archival PDF.** The export filter takes its options on the command
  line as `'pdf:writer_pdf_Export:{"SelectPdfVersion":{"type":"long","value":"2"}}'`
  (the page's example sets 15 on a drawing; the form is the same).
  `SelectPdfVersion`: 0 is PDF 1.7 and the default, 1 is PDF/A-1b, 2 is
  PDF/A-2b, 3 is PDF/A-3b. The Preservation copy asks for 2: PDF/A-2b, the
  kind made for long keeping, with every font inside the file.
  https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html
- **Pictures in the PDF.** By default a picture is written as JPEG at quality
  90 (`UseLosslessCompression` false, `Quality` 90) and its resolution is left
  alone (`ReduceImageResolution` false, `MaxImageResolution` 300 when it is
  turned on). Same page. The Word exports carry the office logo on the cover,
  so this decides much of a PDF's weight.

## The typefaces

The Word exports name Calibri for the text and Consolas for the times
(`app/core/exports.py`). Neither is free and neither is in the image.

- **Calibri.** Debian's `fonts-crosextra-carlito` 20230309-2 is a "sans-serif
  font metric-compatible with Calibri font", in regular, bold, italic and bold
  italic, 2.7 MB installed. Metric-compatible means every letter is as wide as
  Calibri's, so lines and pages break where Word breaks them.
  https://packages.debian.org/trixie/fonts-crosextra-carlito
- **Consolas.** No metric-compatible free face was found. DejaVu Sans Mono is
  already in the image; the build maps Consolas to it and checks the times
  still sit in their column.

## The build's proof, with the network cut

The app image's build runs one conversion by the app's own command under
`RUN --network=none`, which Docker's reference describes as "Run with no
network access" and lists among the `RUN` options from Dockerfile version 1.3,
with no experimental syntax line needed.
https://docs.docker.com/reference/dockerfile/ (the "RUN --network" section,
read 17 November 2026). The server's Docker Engine 29 builds with BuildKit and
a newer built-in Dockerfile version than that.

## Not yet known, and measured by the first build

- What a transcript weighs as a PDF, with and without the office logo, and so
  how many transcripts fit under an office's mail limit.
- How long one conversion takes, and many in one start.
- How much the app image grows.
- Whether every layout comes through: the cover, the tables, the page numbers
  in the footer, the grey citations, the processing record.
- That a PDF/A-2b from this route passes a checker (veraPDF is the free one;
  to be read about before it is relied on).
