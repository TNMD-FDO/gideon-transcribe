# The Dependabot alerts of 2026-09-19

What GitHub's dependency scanner raised against this repository, what each
alert means on this server, and what it would take to clear it. Read with
`docs/research/whisperx-pinned-stack.md`, which is why the stack is pinned
where it is. Written from the alerts as GitHub listed them on 2026-09-19
(`gh api repos/TNMD-FDO/gideon-transcribe/dependabot/alerts?state=open`).

## What Dependabot is

GitHub reads the pinned package lists in the repository and compares each pin
with a public list of published flaws (the GitHub Advisory Database). A pin at
or below a flawed version raises an alert on the repository's Security tab,
with the version that fixes it. The scanner knows nothing about how the
package is used, whether the flawed code runs, or who can reach it; that is
what this note adds.

## The seven alerts

All seven are in the WhisperX service's pins, none in the app's.

| Alert | Severity | Package, pinned | Fixed in | The flaw, in a sentence |
|---|---|---|---|---|
| 7 | high | transformers 4.57.6 | 5.10.0 | `save_pretrained` can write a file outside the folder when a chat template's name carries a path |
| 6 | high | transformers 4.57.6 | 5.5.0 | loading a LightGlue model (a picture-matching model) can run code from the model's files |
| 5 | high | transformers 4.57.6 | 5.3.0 | loading a model whose files carry code can run that code |
| 4 | medium | transformers 4.57.6 | 5.0.0rc3 | the `Trainer` class can run code from a training configuration |
| 3 | low | torch 2.8.0 | 2.13.0 | `torch.jit.script` can corrupt memory on crafted input |
| 2 | low | torch 2.8.0 | 2.10.0 | `torch.lstm_cell` can corrupt memory on crafted input |
| 1 | medium | torch 2.8.0 | 2.9.1 | `unpack_sequence` can corrupt memory on crafted input |

## What each means here

Every one of the seven needs the flawed function to be run on something an
attacker chose: a model's files, a chat template's name, a training
configuration, a TorchScript program, a crafted tensor. On this server none of
those comes from anywhere but this repository:

- **The service takes audio and nothing else.** The app hands it a prepared
  audio file over an internal Docker network, with a token, and reads back
  words. Nobody outside the building can reach the service, and the app never
  passes it a model, a template, a configuration or code.
- **The models are pinned and cached.** The Whisper, alignment and diarization
  models are named in the service's own code and fetched once at install into
  the model cache; the service never fetches a model at run time and never
  loads one a person chose (`docs/research/whisperx-pinned-stack.md`).
- **Nothing is trained, saved or scripted.** The service never calls
  `Trainer`, never calls `save_pretrained`, never loads a LightGlue model, and
  never compiles TorchScript. The three torch flaws are in functions the
  service does not call on any input it did not make itself.

So the flawed code either does not run at all, or runs only on data this
repository's own code produced. Somebody who could exploit one of these would
already have to be running code on the server, at which point the flaw adds
nothing. The risk to the office is accepted as low, and this note is the
record of why.

## What clearing them would take

Not a pin bump. The fixes are in torch 2.9.1 and later and transformers 5.x,
and the stack cannot take either yet:

- whisperx 3.8.6 pins `torch~=2.8.0`, so torch 2.9 or later is unresolvable
  until whisperx releases against a newer torch.
- whisperx 3.8.6 caps `huggingface-hub<1.0.0`, and transformers 5.x needs
  `huggingface-hub>=1.5`, so transformers 5.x is unresolvable for the same
  reason.

Forcing either past whisperx's pins would mean running the service on a
combination its maintainers have not tested on the Blackwell card, which is
the exact risk the pinned-stack note exists to avoid. When whisperx publishes
a release that lifts those two pins, the pin set is re-derived by that note's
method, the image rebuilt, and the GPU benchmark gate run by hand on the
server before the Release; the alerts clear with it.

## What to do now

1. Nothing on the server.
2. On GitHub, each alert can be dismissed with the reason "Vulnerable code is
   not actually used", which keeps it on record and stops it counting as
   open; it reopens by itself if the pin ever changes to another affected
   version. The maintainer does this from the Security tab, or with
   `gh api -X PATCH repos/TNMD-FDO/gideon-transcribe/dependabot/alerts/<n>
   -f state=dismissed -f dismissed_reason=not_used -f dismissed_comment=
   "docs/research/dependabot-2026-09-19.md"` for each number.
3. Check whisperx's releases when the pinned stack is next revisited; this
   note is superseded the day the stack moves.

## Sources

- The alerts: GitHub, Security, Dependabot, read 2026-09-19.
- GHSA-xrqw-3rrv-vx5w, GHSA-fgcw-684q-jj6r, GHSA-29pf-2h5f-8g72,
  GHSA-69w3-r845-3855 (transformers); GHSA-rrmf-rvhw-rf47,
  GHSA-qfhq-4f3w-5fph, GHSA-vgrw-7cvw-pwgx (torch), at
  github.com/advisories/<id>.
- `docs/research/whisperx-pinned-stack.md`, the pin set and its reasons.
