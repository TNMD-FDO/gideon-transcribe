"""The command line of the WhisperX service container.

Every command is a word after the image name:

    docker compose run --rm whisperx selftest
    docker compose run --rm whisperx pull
    docker compose run --rm whisperx make-token it

The container's default command is `serve`, which is what `docker compose up`
starts.
"""

from __future__ import annotations

import sys

from service.version import API_VERSION, SERVICE_VERSION

USAGE = f"""The WhisperX service {SERVICE_VERSION}, API {API_VERSION}.

Commands:
  serve              start the API and the model process (the default command)
  pull               fetch every model named in models.yaml and check it
                     against its pin; needs the HuggingFace token
  make-token NAME    generate a Consumer token and add it to the tokens file
  bench FOLDER       run the benchmark gate over a folder of prepared audio
  selftest           report what this container can see: the GPU, the pinned
                     versions, ffmpeg, and the mounted folders
  version            print the service and API versions
"""

# The commands this version of the image does not carry yet. Each one names the
# document that says what it will do, so that nobody has to guess whether it is
# missing or broken.
NOT_BUILT_YET = {
    "serve": "the API under /v1/ (docs/whisperx-api.md)",
    "pull": "the model pull (docs/whisperx-api.md, 'The pull command')",
    "make-token": "the Consumer token file (docs/whisperx-api.md, 'Tokens')",
    "bench": "the benchmark gate (specification, Phase 1, chapter 16)",
}


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "serve"

    if command in ("-h", "--help", "help"):
        print(USAGE, end="")
        return 0

    if command == "version":
        print(f"{SERVICE_VERSION} (API {API_VERSION})")
        return 0

    if command == "selftest":
        from service.selftest import selftest

        return selftest()

    if command in NOT_BUILT_YET:
        print(
            f"'{command}' is not built yet in service {SERVICE_VERSION}. "
            f"It will be {NOT_BUILT_YET[command]}.",
            file=sys.stderr,
        )
        return 2

    print(f"Unknown command '{command}'.\n", file=sys.stderr)
    print(USAGE, end="", file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
