"""The voices model's pull (v1.139.1): the revision is the snapshot folder's
name, read from the path as the hub gives it; the file inside is a link
into the blob store, and resolving it had named the wrong folder and failed
every pull on the office's server."""

import sys
import types

from service import pull

REVISION = "0dc382f40121a5fbd34db10a2bb04d826c2be6a8"


def a_snapshot(tmp_path):
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    blob = blobs / ("e8" * 32)
    blob.write_bytes(b"weights")
    snapshot = tmp_path / "snapshots" / REVISION
    snapshot.mkdir(parents=True)
    file = snapshot / "speakerverification_en_titanet_large.nemo"
    try:
        file.symlink_to(blob)
    except OSError:
        file.write_bytes(b"weights")
    return file


def test_the_revision_is_the_snapshot_folders_name(monkeypatch, tmp_path):
    file = a_snapshot(tmp_path)
    # The hub's package is not on a test machine; the pull imports it inside.
    hub = types.ModuleType("huggingface_hub")
    hub.hf_hub_download = lambda repo, filename, revision=None: str(file)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    said = []
    monkeypatch.setattr(pull, "_say", lambda line="": said.append(line))
    model = {"repository": "nvidia/x", "revision": REVISION, "file": file.name}
    assert pull._pull_voices(model) == []
    assert any("at its pinned revision" in line for line in said)
    model["revision"] = "f" * 40
    assert pull._pull_voices(model) == [
        "the voices model is not at the revision it is pinned to"
    ]
