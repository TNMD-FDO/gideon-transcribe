# Documents beside the cameras: the reader, the renderer and the OCR engine

What Phase 8 chapter 4 (part 1, v1.71.0) reads a PDF with, why these and not
others, what they cost the image, and what is measured on the server before
part 2 is built. Everything here runs inside the app image on the CPU; nothing
is fetched at run time and nothing leaves the building.

## The pieces

| Package | Version | What it does here | Licence |
|---|---|---|---|
| pdfplumber | 0.11.10 | Opens a PDF and gives each page's words with their positions (`extract_words`), which the paragraph splitter and the picture overlay need | MIT |
| pdfminer.six | 20260107 | pdfplumber's reader underneath; pure Python | MIT |
| pypdfium2 | 5.13.0 | Draws a page to a picture (`page.to_image`), and counts a file's pages at upload before it is kept; a wheel carrying Google's PDFium, no compiler | Apache-2.0 or BSD-3-Clause |
| Pillow | 12.3.0 | The picture in memory, saved as PNG; passed to the OCR bridge | MIT-CMU |
| pytesseract | 0.3.13 | Calls the Tesseract program on a page's picture and returns each word with its box and confidence (`image_to_data`) | Apache-2.0 |
| Tesseract OCR, English data | Debian 13's `tesseract-ocr`, `tesseract-ocr-eng` | Reads a scanned page's words; a separate program, called per page | Apache-2.0 |

Read from: pypi.org/project/pdfplumber, pypi.org/project/pypdfium2,
pypi.org/project/pytesseract, packages.debian.org/trixie/tesseract-ocr, all on
2026-09-19.

## Why these

- **Words with positions, not text alone.** The chapter cites by paragraph and
  lights the paragraph on the real page, so the reader has to say where each
  word sits. `pypdf` and `pdftotext` give text; pdfplumber gives words with
  boxes, over the same pdfminer that has read PDFs in Python for fifteen
  years.
- **One renderer, already a dependency.** pdfplumber draws pages through
  pypdfium2, so the page pictures cost no extra package. PDFium is what Chrome
  reads PDFs with; the wheel needs no system library.
- **OCR as a program, not a model.** Tesseract is Debian's own package, CPU
  only, with English data of a few megabytes. No GPU, no download at run time,
  no language pack beyond English until asked for. pytesseract is the thin
  bridge and nothing more.
- **Not chosen.** OCR models that need PyTorch or a GPU (the WhisperX image has
  the GPU and is pinned for a reason); services; anything that phones home.

## What it costs the image

Measured on the build of v1.71.0 (to be filled in from the server's
`./transcribe upgrade v1.71.0` output): the app image before, after, and the
difference. Expected: about a hundred megabytes for Tesseract and its English
data plus the PDFium wheel.

## The rules in code

- A page with fewer than 8 words of its own is read by OCR (at 220 dots an
  inch); an OCR'd page with fewer than 20 words or a mean confidence under 55
  is **poorly read**.
- A paragraph breaks at a vertical gap of more than nine tenths of a line, or
  at a line indented by more than 1.2 lines' height that follows a line
  ending short of it. Paragraphs are numbered from 1 on each page.
- The picture is drawn at 110 dots an inch: a US Letter page is 935 by 1210
  pixels, about 150 kilobytes as PNG for a text page and up to 400 for a scan.

## What is measured on the server before part 2

To be recorded here after the first real report and the first real scan are
put through v1.71.0 on the office's server:

1. A text PDF from the agency: pages, seconds to read, the paragraph count
   per page against what a reader would count, any paragraph split or joined
   wrongly and why (tables, two columns, headers and footers).
2. A scanned report: pages, seconds to read (OCR is the slow step; expect a
   few seconds a page on the server's CPU), the poorly read count, and three
   paragraphs checked word by word against the picture.
3. The image's size before and after.

Part 2 (the Report tab and Gideon's citations) is written against these
figures, in particular the paragraph splitter's rules for the agency's report
layout and the reading ceiling's default.
