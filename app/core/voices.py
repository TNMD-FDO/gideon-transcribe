"""The voice step (ADR 0021, the voice plan's second release, v1.139.0).

The Speaker check reads words; this module gives it ears. For a Transcript
whose Recording type the office has the voice on for, each line's own words
are cut from the prepared audio by the WhisperX service's diarizer container
(TitaNet-large, `docs/whisperx-api.md`, the voices request) and come back as
a vector; each Speaker's print on the recording is the mean of its lines of
two seconds or more, outliers dropped (rule B of
`docs/research/speaker-verification.md`). Calibrated on the recording's own
lines, the voice then says of every move the words propose **agrees**,
**against** or **cannot tell**, proposes moves of its own under a cap, and
finds a Hand-over: a second voice under one label from a time.

The vectors live on the check's run (`SpeakerCheck.voices`) while its
proposals are pending, so an acceptance can re-score the rest, and are
deleted when the check is done. Nothing of a voice is kept on the Transcript
or anywhere else; nothing is logged but counts.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict

import numpy as np

from core import call_system, settings_store, whisperx

log = logging.getLogger(__name__)

AGREES, AGAINST, CANNOT = "agrees", "against", "cannot tell"
# Rule B: a line joins its Speaker's print from two seconds of speech.
SURE_SECONDS = 2.0
# Under the floor the voice says cannot tell. 1.5 seconds as shipped; the
# measurement found 1 second right on the office's calls and over-reaching
# on a body camera, so a call's floor is lower (ADR 0021, decision 2).
FLOOR_SECONDS = 1.5
FLOORS_BY_TYPE = {"jail call": 1.0, "phone call": 1.0}
# The most moves the voice proposes on its own in one run.
CAP = 15
# A Hand-over: two or three voices under one label, each of three lines and
# ten seconds, apart by the recording's own measure, in time order on eight
# in ten lines, and not differing mainly in loudness.
HANDOVER_LEAST_LINES = 3
HANDOVER_LEAST_SECONDS = 10.0
HANDOVER_TIME_PURITY = 0.8
HANDOVER_LOUDNESS_DB = 6.0
HANDOVER_POOL = 8
MIN_MEMBERS = 3
PAD = 0.03
VOICES_TIMEOUT = 600


class Unavailable(Exception):
    """The voices could not be read; the check runs on words alone."""


# Which recordings --------------------------------------------------------------------


def types_on() -> set[str]:
    return {line.casefold() for line in settings_store.lines_of("voices_types")}


def on_for(recording) -> bool:
    """Whether the voice helps the check on this Recording: its type is on
    the Admin's list. A Recording with no type is never on."""
    kind = (recording.recording_type or "").strip().casefold()
    return bool(kind) and kind in types_on()


def floor_for(recording) -> float:
    kind = (recording.recording_type or "").strip().casefold()
    return FLOORS_BY_TYPE.get(kind, FLOOR_SECONDS)


def bucket_of(net: float, floor: float) -> str:
    if net < floor:
        return "short"
    if net < SURE_SECONDS:
        return "middle"
    return "long"


# The stretches the service is asked about --------------------------------------------


def own_spans(segment) -> tuple[list[list[float]], bool]:
    """A line's own words: the timed words the diarizer gave to the line's
    own label (or to nobody), each padded a little; the whole line when no
    word was timed. Returns the spans and whether they came from words."""
    own = segment.speaker_label or ""
    spans = []
    for word in segment.words or []:
        if (
            not isinstance(word, dict)
            or word.get("start") is None
            or word.get("end") is None
        ):
            continue
        label = word.get("speaker") or own
        if label != own:
            continue
        spans.append([max(0.0, float(word["start"]) - PAD), float(word["end"]) + PAD])
    if spans:
        return spans, True
    return [[float(segment.start), float(segment.end)]], False


def stretches_of(transcript) -> dict[int, list[dict]]:
    """Per Side number, the stretches for the voices request: one per line,
    the other Side's copies and the Call system's lines left out."""
    by_side: dict[int, list[dict]] = defaultdict(list)
    sides = {side.pk: side.number for side in transcript.recording.sides.all()}
    for segment in (
        transcript.segments.filter(same_as_other_side=False)
        .exclude(speaker="")
        .order_by("start", "id")
    ):
        if call_system.is_system(segment.speaker):
            continue
        spans, timed = own_spans(segment)
        number = sides.get(segment.side_id) or (
            next(iter(sides.values())) if len(sides) == 1 else 1
        )
        by_side[number].append(
            {
                "id": str(segment.pk),
                "label": segment.speaker,
                "spans": spans,
                "timed": timed,
                "start": segment.start,
            }
        )
    return by_side


def ask(transcript) -> dict:
    """The service's answer for every Side, merged: the stretches by segment
    id, each with its vector, net seconds and loudness. Raises Unavailable."""
    recording = transcript.recording
    by_side = stretches_of(transcript)
    sides = {side.number: side for side in recording.sides.all()}
    stretches: dict[str, dict] = {}
    labels: dict[tuple, dict] = {}
    cost = {"seconds": 0.0, "card_peak_gb": 0.0, "sides": 0, "model": None}
    for number, rows in by_side.items():
        side = sides.get(number)
        path = side.asr_path if side is not None else None
        if path is None or not path.exists():
            raise Unavailable("the prepared audio is not on disk")
        asked = {
            "stretches": [
                {"id": r["id"], "label": r["label"], "spans": r["spans"]} for r in rows
            ],
            "sure_seconds": SURE_SECONDS,
        }
        try:
            answer = whisperx.voices(path, asked, lane=whisperx.lane_for(recording))
        except whisperx.ServiceError as error:
            raise Unavailable(str(error)) from error
        timed = {r["id"]: r["timed"] for r in rows}
        starts = {r["id"]: r["start"] for r in rows}
        for one in answer.get("stretches", []):
            stretches[one["id"]] = {
                "side": number,
                "label": one["label"],
                "net": float(one.get("net_seconds") or 0.0),
                "rms": one.get("rms_dbfs"),
                "vector": one.get("vector"),
                "timed": timed.get(one["id"], False),
                "start": starts.get(one["id"], 0.0),
            }
        for one in answer.get("labels", []):
            labels[(number, one["label"])] = one
        cost["seconds"] += float(answer.get("seconds") or 0.0)
        cost["card_peak_gb"] = max(
            cost["card_peak_gb"], float(answer.get("card_peak_gb") or 0.0)
        )
        cost["sides"] += 1
        cost["model"] = answer.get("model")
    if not stretches:
        raise Unavailable("no lines to read")
    return {"stretches": stretches, "cost": cost}


# The judge ---------------------------------------------------------------------------


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n else v


def _centroid(vectors: list[np.ndarray]) -> tuple[np.ndarray | None, int]:
    kept = [_unit(np.asarray(v, dtype="float32")) for v in vectors]
    total = len(kept)
    if total < MIN_MEMBERS:
        return None, 0
    for _ in range(10):
        matrix = np.stack(kept)
        centre = _unit(matrix.mean(axis=0))
        cos = matrix @ centre
        median = float(np.median(cos))
        mad = float(np.median(np.abs(cos - median))) * 1.4826
        cut = median - 2.5 * max(mad, 0.01)
        keep = [v for v, s in zip(kept, cos, strict=True) if s >= cut]
        if len(keep) < max(MIN_MEMBERS, int(0.6 * total)) or len(keep) == len(kept):
            break
        kept = keep
    return _unit(np.stack(kept).mean(axis=0)), len(kept)


class Judge:
    """The voice's answers for one Transcript, from the vectors and the
    Speakers as they stand now (names change as a person accepts, so the
    prints are rebuilt from the stored vectors each time)."""

    def __init__(self, transcript, stretches: dict[str, dict], floor: float):
        self.floor = floor
        self.names: dict[str, str] = {}
        for pk, name in transcript.segments.filter(
            same_as_other_side=False
        ).values_list("pk", "speaker"):
            self.names[str(pk)] = name
        self.stretches = {
            sid: row
            for sid, row in stretches.items()
            if row.get("vector")
            and self.names.get(sid)
            and not call_system.is_system(self.names[sid])
        }
        self.vec = {
            sid: _unit(np.asarray(row["vector"], dtype="float32"))
            for sid, row in self.stretches.items()
        }
        self.members: dict[tuple, list[str]] = {}
        self.centroids: dict[tuple, np.ndarray] = {}
        pool: dict[tuple, list[str]] = defaultdict(list)
        for sid, row in self.stretches.items():
            if row["timed"] and row["net"] >= SURE_SECONDS:
                pool[(row["side"], self.names[sid])].append(sid)
        for key, ids in pool.items():
            centre, kept = _centroid([self.vec[i] for i in ids])
            if centre is not None:
                self.centroids[key] = centre
                self.members[key] = ids[:kept] if kept == len(ids) else ids
        self.calibration = self._calibrate()

    def name_of(self, sid: str) -> str:
        return self.names.get(sid, "")

    def key_for(self, sid: str, name: str) -> tuple | None:
        side = self.stretches[sid]["side"]
        if (side, name) in self.centroids:
            return (side, name)
        return next((k for k in sorted(self.centroids, key=str) if k[1] == name), None)

    def cos_to(self, sid: str, name: str) -> float | None:
        key = self.key_for(sid, name)
        if key is None:
            return None
        members = self.members.get(key, [])
        v = self.vec[sid]
        if sid in members:
            if len(members) <= MIN_MEMBERS:
                return None
            total = np.stack([self.vec[i] for i in members]).sum(axis=0) - v
            return float(v @ _unit(total))
        return float(v @ self.centroids[key])

    def others_for(self, sid: str) -> list[tuple]:
        own = self.name_of(sid)
        side = self.stretches[sid]["side"]
        same = [k for k in self.centroids if k[0] == side and k[1] != own]
        if same:
            return sorted(same, key=str)
        return sorted((k for k in self.centroids if k[1] != own), key=str)

    def scores(self, sid: str) -> dict | None:
        own = self.name_of(sid)
        if sid not in self.stretches or not own:
            return None
        cos_own = self.cos_to(sid, own)
        others = self.others_for(sid)
        if cos_own is None or not others:
            return None
        best_name, best = None, -2.0
        for key in others:
            s = self.cos_to(sid, key[1])
            if s is not None and s > best:
                best_name, best = key[1], s
        if best_name is None:
            return None
        return {
            "own": cos_own,
            "other": best,
            "other_name": best_name,
            "margin": cos_own - best,
        }

    def _calibrate(self) -> dict:
        margins: dict[str, list[float]] = {"short": [], "middle": [], "long": []}
        same: list[float] = []
        different: list[float] = []
        for sid, row in self.stretches.items():
            if not row["timed"]:
                continue
            s = self.scores(sid)
            if s is None:
                continue
            margins[bucket_of(row["net"], self.floor)].append(s["margin"])
            if row["net"] >= SURE_SECONDS:
                same.append(s["own"])
                different.append(s["other"])
        out: dict = {
            "thresholds": {},
            "midpoint": None,
            "lines": {b: len(v) for b, v in margins.items()},
        }
        if same and different:
            out["midpoint"] = round(
                (float(np.median(same)) + float(np.median(different))) / 2, 3
            )
        last = None
        for b in ("long", "middle", "short"):
            values = margins[b]
            if len(values) >= 5:
                arr = np.array(values)
                # Firm is a flipped margin as big as a right line's small
                # margins: the tenth percentile, but never more than half
                # the typical one (voices far apart would otherwise ask for
                # a flip as big as the whole separation), and never under 0.02.
                tenth = float(np.percentile(arr, 10))
                median = max(float(np.median(arr)), 0.0)
                threshold = tenth if tenth > 0 else 0.25 * median
                if median > 0:
                    threshold = min(threshold, 0.5 * median)
                out["thresholds"][b] = round(max(threshold, 0.02), 3)
                last = out["thresholds"][b]
            else:
                out["thresholds"][b] = last
        return out

    def threshold(self, net: float) -> float | None:
        return self.calibration["thresholds"].get(bucket_of(net, self.floor))

    def word(self, segment_id, from_: str, to: str) -> tuple[str, str]:
        """The voice's word on a move, and the note the page shows."""
        sid = str(segment_id)
        row = self.stretches.get(sid)
        if row is None:
            return CANNOT, "Voice: this line was not read."
        if row["net"] < self.floor:
            return CANNOT, f"Voice: too short to judge ({row['net']:.1f} s of speech)."
        a = self.cos_to(sid, from_)
        b = self.cos_to(sid, to)
        t = self.threshold(row["net"])
        if a is None or b is None or t is None:
            return CANNOT, "Voice: not enough of one of these speakers to compare with."
        d = b - a
        if d >= t:
            return AGREES, f"Voice: this line sounds like {to}."
        if d <= -t:
            return AGAINST, f"Voice: this line sounds like {from_}, not {to}."
        return CANNOT, "Voice: the two speakers sound alike on this line."

    def own_proposals(self, taken: set, cap: int = CAP) -> list[dict]:
        """Lines far from their own print and near another's, that the
        words never flagged, under the cap."""
        found = []
        for sid, row in self.stretches.items():
            if int(sid) in taken or not row["timed"] or row["net"] < self.floor:
                continue
            s = self.scores(sid)
            t = self.threshold(row["net"])
            if s is None or t is None or s["margin"] > -t:
                continue
            found.append((s["margin"], sid, s["other_name"]))
        found.sort()
        return [
            {
                "segment_id": int(sid),
                "from": self.name_of(sid),
                "to": other,
                "margin": round(m, 3),
            }
            for m, sid, other in found[:cap]
        ]

    def unsure_lines(self, taken: set, cap: int = 40) -> list[dict]:
        """Lines the voice cannot tell between two speakers (v1.145.0):
        long enough to judge, their margin inside the threshold either way,
        the smallest margins first, under a cap."""
        found = []
        for sid, row in self.stretches.items():
            if int(sid) in taken or not row["timed"] or row["net"] < self.floor:
                continue
            s = self.scores(sid)
            t = self.threshold(row["net"])
            if s is None or t is None or abs(s["margin"]) >= t:
                continue
            found.append((abs(s["margin"]), sid, s["other_name"]))
        found.sort()
        return [
            {"segment_id": int(sid), "from": self.name_of(sid), "to": other}
            for _m, sid, other in found[:cap]
        ]

    def handovers(self) -> list[dict]:
        """Two or three voices under one label, apart and in time order,
        not differing mainly in loudness."""
        midpoint = self.calibration.get("midpoint")
        if midpoint is None:
            return []
        found = []
        for (side, name), _ids in self.members.items():
            pool = [
                sid
                for sid, row in self.stretches.items()
                if row["side"] == side
                and self.name_of(sid) == name
                and row["timed"]
                and row["net"] >= self.floor
            ]
            if len(pool) < HANDOVER_POOL:
                continue
            matrix = np.stack([self.vec[sid] for sid in pool])
            chosen = None
            for k in (3, 2):
                if len(pool) < 4 * k:
                    continue
                labels = _kmeans(matrix, k, seed=len(pool) + k)
                clusters = [
                    [pool[i] for i in range(len(pool)) if labels[i] == j]
                    for j in range(k)
                ]
                if any(
                    len(c) < HANDOVER_LEAST_LINES
                    or sum(self.stretches[s]["net"] for s in c) < HANDOVER_LEAST_SECONDS
                    for c in clusters
                ):
                    continue
                centres = [
                    _unit(np.stack([self.vec[s] for s in c]).mean(axis=0))
                    for c in clusters
                ]
                if all(
                    float(centres[a] @ centres[b]) < midpoint
                    for a in range(k)
                    for b in range(a + 1, k)
                ):
                    chosen = clusters
                    break
            if chosen is None:
                continue
            chosen.sort(
                key=lambda c: float(np.median([self.stretches[s]["start"] for s in c]))
            )
            for first, second in zip(chosen[:-1], chosen[1:], strict=False):
                at, purity = _split_time(first, second, self.stretches)
                if at is None or purity < HANDOVER_TIME_PURITY:
                    break
                loud_a = np.mean(
                    [
                        self.stretches[s]["rms"]
                        for s in first
                        if self.stretches[s]["rms"] is not None
                    ]
                    or [0.0]
                )
                loud_b = np.mean(
                    [
                        self.stretches[s]["rms"]
                        for s in second
                        if self.stretches[s]["rms"] is not None
                    ]
                    or [0.0]
                )
                gap = abs(float(loud_a - loud_b))
                found.append(
                    {
                        "speaker": name,
                        "side": side,
                        "at": round(at, 3),
                        "lines_after": len(second),
                        "voices": len(chosen),
                        "loudness_gap_db": round(gap, 1),
                        "held": gap >= HANDOVER_LOUDNESS_DB,
                    }
                )
        return found


def _kmeans(matrix: np.ndarray, k: int, seed: int) -> np.ndarray:
    best, best_score = None, -1e9
    rng = np.random.default_rng(seed)
    for _ in range(5):
        centres = matrix[rng.choice(len(matrix), k, replace=False)].copy()
        labels = np.zeros(len(matrix), dtype=int)
        for turn in range(30):
            new = (matrix @ centres.T).argmax(axis=1)
            if turn and (new == labels).all():
                break
            labels = new
            for j in range(k):
                if (labels == j).any():
                    centres[j] = _unit(matrix[labels == j].mean(axis=0))
        score = float((matrix @ centres.T).max(axis=1).sum())
        if score > best_score and all((labels == j).any() for j in range(k)):
            best, best_score = labels.copy(), score
    return best if best is not None else np.zeros(len(matrix), dtype=int)


def _split_time(
    first: list[str], second: list[str], stretches: dict
) -> tuple[float | None, float]:
    best_t, best_purity = None, 0.0
    for t in sorted({stretches[s]["start"] for s in first + second}):
        n = sum(1 for s in first if stretches[s]["start"] < t) + sum(
            1 for s in second if stretches[s]["start"] >= t
        )
        purity = n / max(1, len(first) + len(second))
        if purity > best_purity:
            best_t, best_purity = t, purity
    return best_t, best_purity


# What the check keeps and reads back -------------------------------------------------


def dump(answer: dict) -> dict:
    """What the run keeps while its proposals are pending: the vectors by
    segment id, rounded, and the cost. Deleted when the check is done."""
    return {
        "stretches": {
            sid: {
                "side": row["side"],
                "net": row["net"],
                "rms": row["rms"],
                "timed": row["timed"],
                "start": row["start"],
                "vector": [round(float(x), 5) for x in row["vector"]]
                if row.get("vector")
                else None,
            }
            for sid, row in answer["stretches"].items()
        },
        "cost": answer["cost"],
    }


def judge_from(transcript, kept: dict) -> Judge | None:
    """The judge rebuilt from what a run kept, with the Speakers as they
    stand now; None when nothing was kept."""
    stretches = (kept or {}).get("stretches") or {}
    if not stretches:
        return None
    return Judge(transcript, stretches, floor_for(transcript.recording))


def counts(judge: Judge) -> dict:
    return {
        "lines_read": len(judge.stretches),
        "prints": len(judge.centroids),
        "calibration": judge.calibration,
        "floor": judge.floor,
    }


def summary_words(rows) -> Counter:
    return Counter(one.voice or "silent" for one in rows)
