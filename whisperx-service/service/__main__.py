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
  make-token NAME    print a token line for a new Consumer, to add to the
                     tokens file; add --admin for a token that can see and
                     cancel every Consumer's jobs
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
    "bench": "the benchmark gate (specification, Phase 1, chapter 16)",
}


def make_token(argv: list[str]) -> int:
    """Print a line for the tokens file. It is never written from in here.

    The tokens file reaches this container as a read-only secret, which is
    right: a running service should not be able to add Consumers to itself. So
    the command makes the line and a person puts it in the file. On a full
    installation `./transcribe make-token` does both in one step.
    """
    from service.tokens import Consumer, format_line, new_token

    names = [word for word in argv if not word.startswith("-")]
    flags = [word for word in argv if word.startswith("-")]
    unknown = [flag for flag in flags if flag != "--admin"]

    if len(names) != 1 or unknown:
        print("Usage: make-token NAME [--admin]", file=sys.stderr)
        return 64

    consumer = Consumer(name=names[0], token=new_token(), admin="--admin" in flags)
    line = format_line(consumer)

    print(f"A token for the Consumer '{consumer.name}'.")
    print()
    print("Add this line to whisperx-service/secrets/tokens on the server:")
    print()
    print(f"    {line}")
    print()
    print("The service picks the change up on its own; nothing needs restarting.")
    print("The token is not stored anywhere else and is not shown again, so give")
    print("it to whoever asked for it and keep a copy in the office's password")
    print("store.")
    return 0


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "serve"
    rest = argv[1:]

    if command in ("-h", "--help", "help"):
        print(USAGE, end="")
        return 0

    if command == "version":
        print(f"{SERVICE_VERSION} (API {API_VERSION})")
        return 0

    if command == "selftest":
        from service.selftest import selftest

        return selftest()

    if command == "pull":
        from service.pull import pull

        return pull()

    if command == "make-token":
        return make_token(rest)

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
