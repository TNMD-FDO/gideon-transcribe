"""The PDF maker (Phase 14 chapter 1; docs/research/pdf-maker.md).

The app writes Word and nothing else; a Preservation copy wants PDF. This
turns Word files into PDF/A-2b with LibreOffice Writer, run as a command with
no screen: one start for a batch of files, each start with a profile of its
own that is removed after, so two batches at once never share one. Nothing
here reaches outside the container: Debian builds LibreOffice with its update
check off, and the image's build proves a conversion with no network.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("transcribe.pdf")

# PDF/A-2b: `SelectPdfVersion` 2 (0 is plain PDF 1.7, 1 is PDF/A-1b).
FILTER = 'pdf:writer_pdf_Export:{"SelectPdfVersion":{"type":"long","value":"2"}}'

# What one start may take: a floor for LibreOffice itself to come up, and so
# long again for each file. A transcript of a long recording is hundreds of
# pages and still converts in seconds; this is the limit for a stuck start.
SECONDS_TO_START = 60
SECONDS_A_FILE = 60

NOT_INSTALLED = (
    "The PDF maker is not in this build, so a Preservation copy cannot be made here."
)


class Failed(Exception):
    """A file that did not become a PDF, said in plain words."""


def binary() -> str | None:
    """Where LibreOffice is, or None in a build without it (a development
    machine; every image has it, and the image's build proves it)."""
    return shutil.which("soffice")


def installed() -> bool:
    return binary() is not None


def convert(sources: list[Path], out_dir: Path) -> list[Path]:
    """Each Word file as a PDF/A of the same stem in `out_dir`, in order.

    All of them or none: one that did not come out fails the batch, with its
    name, since a copy with a hole in it is worse than none.
    """
    program = binary()
    if program is None:
        raise Failed(NOT_INSTALLED)
    if not sources:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="transcribe-pdf-profile-"))
    command = [
        program,
        "--headless",
        "--norestore",
        "--nolockcheck",
        f"-env:UserInstallation={profile.as_uri()}",
        "--convert-to",
        FILTER,
        "--outdir",
        str(out_dir),
        *[str(one) for one in sources],
    ]
    try:
        done = subprocess.run(  # noqa: S603 (our own command, no shell)
            command,
            capture_output=True,
            timeout=SECONDS_TO_START + SECONDS_A_FILE * len(sources),
            # A home of its own: LibreOffice writes there and nowhere else.
            env={**os.environ, "HOME": str(profile)},
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise Failed("The PDF maker took too long and was stopped.") from None
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    made = [out_dir / f"{one.stem}.pdf" for one in sources]
    for source, pdf in zip(sources, made, strict=True):
        if not pdf.exists() or pdf.stat().st_size == 0:
            log.warning(
                "no PDF for %s (exit %s): %s",
                source.name,
                done.returncode,
                (done.stderr or b"").decode("utf-8", "replace")[-400:],
            )
            raise Failed(f"{source.stem} could not be turned into a PDF.")
    return made
