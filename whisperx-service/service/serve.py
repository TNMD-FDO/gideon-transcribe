"""Starting the service: the line, the model process, the API, the sweeper.

This is what `docker compose up` runs. It puts the line back in order first,
because a service that stopped part way through a job has to decide what
becomes of that job before it accepts another.
"""

from __future__ import annotations

import logging
import threading
import time

from service.api import create_app
from service.auth import Tokens
from service.models_file import Models
from service.runner import Runner
from service.settings import Settings
from service.store import Store

# How often results past their day and rows past their month are cleared away.
SWEEP_SECONDS = 600

PORT = 8000

log = logging.getLogger("whisperx")


def _sweeper(store: Store, stop: threading.Event) -> None:
    while not stop.wait(SWEEP_SECONDS):
        try:
            results, rows = store.sweep()
            if results or rows:
                log.info("swept %d results and %d job rows", results, rows)
        except Exception:  # noqa: BLE001 - tidying must not stop the service
            log.exception("the sweep stumbled")


def serve() -> int:
    import uvicorn

    settings = Settings.from_environment()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # The journal is never the record and holds no content: job ids, Consumer
    # names, stages, timings, and reason classes only.
    logging.getLogger("uvicorn.access").disabled = True

    store = Store(settings)
    recovered = store.recover()
    for job_id in recovered:
        log.info("job %s was interrupted and goes back to the head of the line", job_id)

    models = Models.load()
    tokens = Tokens(settings.tokens_file)
    runner = Runner(settings, store, models)
    runner.start()

    stop = threading.Event()
    threading.Thread(target=_sweeper, args=(store, stop), daemon=True).start()

    app = create_app(settings, store, tokens, models, runner)
    log.info(
        "the WhisperX service is listening on port %d, batch size %d, "
        "voice activity %.3f/%.3f",
        PORT,
        settings.batch_size,
        settings.vad_onset,
        settings.vad_offset,
    )

    try:
        uvicorn.run(app, host="0.0.0.0", port=PORT, log_config=None)
    finally:
        stop.set()
        runner.stop()
        store.close()
        # Give the model process a moment to be reaped before the container
        # goes, so that nothing is left holding the card.
        time.sleep(0.5)
    return 0
