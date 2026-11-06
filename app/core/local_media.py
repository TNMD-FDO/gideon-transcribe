"""The playback copies served by Django itself, for a local walk alone
(docs/local-walk.md). On a server Caddy serves them with byte ranges and
this module is never wired in: core/urls.py adds its one route only when
run_local.sh sets APP_LOCAL_MEDIA. A browser seeks a video only where the
server honours a Range header, so this answers 206 to one, as Caddy does.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseNotFound

RANGE = re.compile(r"bytes=(\d*)-(\d*)")
TYPES = {".mp4": "video/mp4", ".m4a": "audio/mp4", ".vtt": "text/vtt"}


def serve(request: HttpRequest, path: str) -> HttpResponse:
    root = (Path(settings.DATA_DIR) / "cases").resolve()
    wanted = (root / path).resolve()
    if root not in wanted.parents or not wanted.is_file():
        return HttpResponseNotFound("not found")
    size = os.path.getsize(wanted)
    kind = TYPES.get(wanted.suffix.lower(), "application/octet-stream")
    asked = RANGE.match(request.headers.get("Range", "") or "")
    if not asked:
        # FileResponse closes the handle when the answer is sent.
        answer = FileResponse(open(wanted, "rb"), content_type=kind)  # noqa: SIM115
        answer["Accept-Ranges"] = "bytes"
        answer["Content-Length"] = str(size)
        return answer
    start = int(asked.group(1) or 0)
    end = int(asked.group(2)) if asked.group(2) else size - 1
    end = min(end, size - 1)
    if start > end:
        answer = HttpResponse(status=416)
        answer["Content-Range"] = f"bytes */{size}"
        return answer
    # The generator below closes the handle once the range is sent.
    handle = open(wanted, "rb")  # noqa: SIM115
    handle.seek(start)

    def pieces():
        left = end - start + 1
        while left > 0:
            chunk = handle.read(min(65536, left))
            if not chunk:
                break
            left -= len(chunk)
            yield chunk
        handle.close()

    answer = HttpResponse(pieces(), status=206, content_type=kind)
    answer["Accept-Ranges"] = "bytes"
    answer["Content-Range"] = f"bytes {start}-{end}/{size}"
    answer["Content-Length"] = str(end - start + 1)
    return answer
