"""The voices' arithmetic (ADR 0021): the clip from spans, the loudness, the
label's vector from its sure stretches with outliers dropped. Plain numpy,
no model.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "diarizer"))

import centroids  # noqa: E402


def test_cut_lays_the_spans_end_to_end_and_merges_overlaps():
    audio = np.arange(16000 * 4, dtype="float32")
    clip = centroids.cut(audio, [[1.0, 2.0], [1.5, 2.5], [3.0, 3.5]])
    # 1.0 to 2.5 merged (1.5 s) plus 0.5 s: two seconds of samples.
    assert len(clip) == 16000 * 2
    assert clip[0] == 16000 * 1.0
    assert centroids.net_seconds(clip) == 2.0
    assert len(centroids.cut(audio, [[5.0, 6.0]])) == 0


def test_loudness_reads_both_integer_and_unit_samples():
    loud = np.full(16000, 0.5, dtype="float32")
    quiet = np.full(16000, 0.05, dtype="float32")
    assert centroids.rms_dbfs(loud) > centroids.rms_dbfs(quiet)
    assert (
        abs(
            centroids.rms_dbfs(np.full(16000, 16384, dtype="<i2"))
            - centroids.rms_dbfs(loud)
        )
        < 0.2
    )
    assert centroids.rms_dbfs(np.zeros(0)) is None


def test_a_label_needs_three_sure_stretches():
    rng = np.random.default_rng(1)
    base = rng.normal(size=192)
    rows = [
        {
            "label": "A",
            "net_seconds": 3.0,
            "vector": list(base + rng.normal(scale=0.05, size=192)),
        },
        {
            "label": "A",
            "net_seconds": 3.0,
            "vector": list(base + rng.normal(scale=0.05, size=192)),
        },
        {"label": "A", "net_seconds": 1.0, "vector": list(base)},
    ]
    labels = centroids.labels_from(rows, 2.0)
    assert labels == [
        {"label": "A", "vector": None, "members": 0, "dropped": 0, "sure_stretches": 2}
    ]


def test_an_outlier_is_dropped_and_the_vector_is_unit_length():
    rng = np.random.default_rng(2)
    base = rng.normal(size=192)
    rows = [
        {
            "label": "B",
            "net_seconds": 4.0,
            "vector": list(base + rng.normal(scale=0.05, size=192)),
        }
        for _ in range(8)
    ]
    rows.append({"label": "B", "net_seconds": 4.0, "vector": list(-base)})
    labels = centroids.labels_from(rows, 2.0)
    (row,) = labels
    assert row["members"] == 8 and row["dropped"] == 1 and row["sure_stretches"] == 9
    vector = np.asarray(row["vector"])
    assert abs(np.linalg.norm(vector) - 1.0) < 1e-3
    assert float(vector @ centroids.unit(base)) > 0.99
