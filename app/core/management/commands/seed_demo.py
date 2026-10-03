"""Fill an empty database with a fictional office, for a walk of the pages.

    python manage.py seed_demo --password-file <a file holding the admin's password>

A developer's tool, never run on an office's server: it makes a Local admin
and a second person, cases, recordings with transcripts and speakers, an
incident with three cameras, clips, and names waiting to be accepted, so
that every page has something on it at every screen size. Every name,
address and word here is made up. The recordings' files are stand-ins (no
media worker runs on a workstation), so nothing plays.

It refuses to run where anybody already exists, so it cannot touch a
database that is in use.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core import incidents, settings_store
from core.assistant import Suggestion
from core.cases import Case
from core.clips import Clip, RenderState
from core.jobs import Segment, Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording

ADMIN = "test"
COLLEAGUE = "pat"

# A body camera's lines: who, then what. Fictional, and the same shape as a
# real one so the Speakers page and the suggestions have work to do.
CAMERA_LINES = [
    ("Speaker 1", "Dispatch, unit twelve, we're on scene at the harbour car park."),
    ("Speaker 2", "Evening. Is this your vehicle, sir?"),
    ("Speaker 3", "Yeah, it's mine. What's the problem?"),
    ("Speaker 2", "Your tail light's out and you crossed the line twice back there."),
    ("Speaker 3", "I was looking for the turning, that's all."),
    ("Speaker 1", "Dale, can you get his licence while I run the plate?"),
    ("Speaker 2", "Licence and insurance, please."),
    ("Speaker 3", "It's in the glove box. Can I reach for it?"),
    ("Speaker 2", "Go ahead, slowly."),
    ("Speaker 1", "Plate comes back clean. Registered to a Morgan Whitfield."),
    ("Speaker 3", "That's me. Morgan."),
    ("Speaker 2", "Morgan, have you had anything to drink tonight?"),
    ("Speaker 3", "Two beers with dinner, about eight o'clock."),
    ("Speaker 1", "Step out of the car for me, please."),
    ("Speaker 3", "Is this really necessary?"),
    ("Speaker 2", "It's a few questions and a quick test. Then you're on your way."),
    ("Speaker 4", "Everything all right over here? I'm the manager, I saw the lights."),
    ("Speaker 1", "We're fine, thank you. Can you step back to the doorway?"),
    ("Speaker 4", "Sure. Let me know if you need the camera footage from the lot."),
    (
        "Speaker 2",
        "Morgan, follow the light with your eyes only. Don't move your head.",
    ),
    ("Speaker 3", "Okay."),
    ("Speaker 1", "Riley, I'm going to call this in. Stay with him."),
    ("Speaker 2", "Copy."),
    ("Speaker 3", "Am I being arrested?"),
    ("Speaker 2", "Not right now. We're going to do a breath test next."),
    ("Speaker 3", "Fine. I've got nothing to hide."),
    (
        "Speaker 1",
        "Dispatch, unit twelve, one detained pending a breath test, harbour car park.",
    ),
    ("Speaker 2", "Blow steadily until I say stop."),
    ("Speaker 3", "Like this?"),
    ("Speaker 2", "That's it. Keep going. Stop."),
    ("Speaker 1", "What's it say?"),
    ("Speaker 2", "Under the limit. Morgan, get that tail light fixed this week."),
    ("Speaker 3", "I will. Thank you."),
    ("Speaker 1", "Unit twelve clear, no further action."),
]

# A phone call between two people.
CALL_LINES = [
    ("Side 1", "This call is from a correctional facility and may be recorded."),
    ("Side 2", "Hello?"),
    ("Side 1", "Hey, it's me. Did you get the letter?"),
    ("Side 2", "I got it yesterday. The hearing's on the fourteenth."),
    ("Side 1", "Did Jordan say anything about the witness?"),
    ("Side 2", "Only that she might not come. Her sister's sick."),
    ("Side 1", "Tell her it matters. Tell her I said please."),
    ("Side 2", "I will. Do you need anything on your account?"),
    ("Side 1", "Twenty for the phone, if you can."),
    ("Side 2", "I'll do it Friday. Love you."),
    ("Side 1", "Love you too. Fourteenth, don't forget."),
]

# A dictation, one voice.
MEMO_LINES = [
    ("Speaker 1", "Memo to file, Marsh Lane matter, interview of the neighbour."),
    ("Speaker 1", "She states she heard shouting at around eleven and looked out."),
    ("Speaker 1", "She saw a light-coloured hatchback leave at speed, no plate noted."),
    (
        "Speaker 1",
        "She did not call anyone that night. She spoke to the officer the next day.",
    ),
    ("Speaker 1", "Follow up: the shop on the corner may have a camera over the door."),
    ("Speaker 1", "End of memo."),
]


class Command(BaseCommand):
    help = "Fill an empty database with a fictional office, for a walk of the pages."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--password", default="", help="the Local admin's password")
        parser.add_argument(
            "--password-file",
            default="",
            help="a file holding the Local admin's password, so that it is in no "
            "command line",
        )

    def handle(self, *args, **options) -> None:
        if User.objects.exists():
            self.stdout.write("Somebody already exists here; nothing seeded.")
            return
        password = options["password"]
        if not password and options["password_file"]:
            kept = Path(options["password_file"])
            password = kept.read_text(encoding="utf-8").strip()
        if not password:
            raise CommandError(
                "Give the Local admin's password with --password or --password-file."
            )
        # All or nothing, so a slip leaves an empty database rather than half
        # an office that the next run then refuses to touch.
        with transaction.atomic():
            self.seed(password)

    def seed(self, password: str) -> None:
        for key in (
            "folder_management",
            "incidents",
            "clips_available",
            "assistant_available",
            "suggestions_available",
            "sharing",
            "dictation",
            "live_recording",
        ):
            settings_store.set_to(key, True)

        admin = User.objects.create_local_admin(ADMIN, password)
        colleague = User.objects.create_local_admin(COLLEAGUE, password + "-colleague")
        colleague.display_name = "Pat Okonkwo"
        colleague.save(update_fields=["display_name"])

        harbour = Case.objects.create(owner=admin, name="Harbour Street stop")
        marsh = Case.objects.create(owner=colleague, name="Marsh Lane interview")
        samples = Case.objects.create(
            owner=admin, name="Demo: audio samples (fictional)"
        )

        cameras = []
        for number, (camera, offset) in enumerate(
            (("BWC-1", 0.0), ("BWC-2", 7.0), ("BWC-3", 41.0)), start=1
        ):
            recording = self.video(
                admin,
                harbour,
                f"Officer{number}_202511062025_{camera}-0",
                camera=camera,
                time=f"20:25:{12 + int(offset):02d}",
            )
            self.transcript(recording, CAMERA_LINES, every=14.0, shift=offset)
            cameras.append(recording)
        incident = incidents.make(harbour, "Harbour car park", cameras, by=admin)

        call = self.audio(admin, harbour, "Call_20251107_0915", seconds=312.0)
        call_transcript = self.transcript(call, CALL_LINES, every=9.0)
        first = cameras[0].transcript
        lines = list(first.segments.order_by("start"))
        for speaker, name, basis, line in (
            ("Speaker 2", "Dale", "addressed", 5),
            ("Speaker 3", "Morgan", "introduces", 10),
            ("Speaker 2", "Riley", "addressed", 21),
        ):
            segment = lines[line]
            Suggestion.objects.create(
                transcript=first,
                speaker=speaker,
                name=name,
                basis=basis,
                line=line,
                segment=segment,
                start=segment.start,
                quote=segment.text,
            )
        Suggestion.objects.create(
            transcript=call_transcript,
            speaker="Side 2",
            name="Jordan",
            kind="name",
            confidence="low",
            basis="addressed",
            line=4,
            start=36.0,
            quote=CALL_LINES[4][1],
        )

        self.clip(cameras[0], admin, "Step out of the car", 182.0)
        self.clip(cameras[1], admin, "Breath test", 378.0)
        self.clip(call, admin, "The hearing date", 27.0)

        neighbour = self.audio(
            colleague, marsh, "Neighbour_interview_memo", seconds=95.0
        )
        self.transcript(neighbour, MEMO_LINES, every=15.0)
        self.audio(
            colleague, marsh, "Shop_camera_statement", seconds=640.0, transcript=False
        )

        for number in range(1, 5):
            recording = self.audio(
                admin, samples, f"Sample_{number:02d}", seconds=60.0 * number
            )
            self.transcript(recording, CALL_LINES[: 2 + number], every=10.0)

        loose = self.audio(admin, None, "Voicemail_0412", seconds=48.0)
        self.transcript(loose, CALL_LINES[:3], every=12.0)
        self.audio(admin, None, "Site_visit_notes", seconds=130.0, transcript=False)

        self.stdout.write(
            f"Seeded: {User.objects.count()} people, {Case.objects.count()} cases, "
            f"{Recording.objects.count()} recordings, one incident ({incident.name}), "
            f"{Clip.objects.count()} clips, {Suggestion.objects.count()} names waiting."
        )
        self.stdout.write(f"Sign in as {ADMIN} with the password you gave.")

    # The pieces --------------------------------------------------------------------

    @staticmethod
    def video(person, case, title, *, camera, time, seconds=780.0):
        recording = Recording.objects.create(
            batch=Batch.objects.create(user=person),
            user=person,
            case=case,
            title=title,
            original_filename=f"{title}.mp4",
            media_state=MediaState.READY,
            duration_seconds=seconds,
            playback_ready=True,
            diarize=True,
            recording_type="Body camera",
            stamp={
                "date": "11/06/2025",
                "time": time,
                "camera": camera,
                "at": 2.0,
                "checked": True,
            },
            probe={"format": {"tags": {}}},
        )
        recording.folder.mkdir(parents=True, exist_ok=True)
        (recording.folder / "playback.mp4").write_bytes(b"stand-in, not media")
        return recording

    @staticmethod
    def audio(person, case, title, *, seconds, transcript=True):
        recording = Recording.objects.create(
            batch=Batch.objects.create(user=person),
            user=person,
            case=case,
            title=title,
            original_filename=f"{title}.m4a",
            media_state=MediaState.READY if transcript else MediaState.PREPARING,
            duration_seconds=seconds,
            playback_ready=transcript,
            diarize=True,
        )
        recording.folder.mkdir(parents=True, exist_ok=True)
        if transcript:
            (recording.folder / "playback.m4a").write_bytes(b"stand-in, not sound")
        return recording

    @staticmethod
    def transcript(recording, lines, *, every, shift=0.0):
        made = Transcript.objects.create(recording=recording, language="en")
        for number, (speaker, text) in enumerate(lines):
            start = 12.0 + number * every - shift
            if start < 0:
                continue
            Segment.objects.create(
                transcript=made,
                start=start,
                end=start + min(every - 1.0, 2.0 + len(text) / 14.0),
                text=text,
                speaker=speaker,
                speaker_label=speaker.upper().replace(" ", "_"),
            )
        return made

    @staticmethod
    def clip(recording, person, title, start):
        clip = Clip.objects.create(
            recording=recording,
            user=person,
            title=title,
            start=start,
            end=start + 20.0,
            state=RenderState.READY,
            include_excerpt=False,
        )
        clip.folder.mkdir(parents=True, exist_ok=True)
        clip.path.write_bytes(b"stand-in, not sound")
        return clip
