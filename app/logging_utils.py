import logging
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Event, Thread
from time import perf_counter
from typing import Iterator

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


def configure_app_logging() -> None:
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False

    if any(getattr(handler, "_deepdive_console_handler", False) for handler in app_logger.handlers):
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler._deepdive_console_handler = True
    app_logger.addHandler(handler)
    app_logger.info("DeepDive application logging configured level=INFO")


def _format_fields(fields: dict[str, object]) -> str:
    if not fields:
        return ""
    return " " + " ".join(f"{key}={value}" for key, value in fields.items())


@contextmanager
def log_stage(
    logger: logging.Logger,
    stage: str,
    heartbeat_interval_seconds: float | None = None,
    **fields: object,
) -> Iterator[None]:
    request_id = request_id_context.get()
    started_at = perf_counter()
    logger.info(
        "request_id=%s stage=%s event=started%s",
        request_id,
        stage,
        _format_fields(fields),
    )
    heartbeat_stop = Event()
    heartbeat_thread = None
    if heartbeat_interval_seconds is not None:
        def log_heartbeat() -> None:
            while not heartbeat_stop.wait(heartbeat_interval_seconds):
                logger.info(
                    "request_id=%s stage=%s event=still_running elapsed_ms=%.1f%s",
                    request_id,
                    stage,
                    (perf_counter() - started_at) * 1000,
                    _format_fields(fields),
                )

        heartbeat_thread = Thread(
            target=log_heartbeat,
            name=f"deepdive-{stage}-heartbeat",
            daemon=True,
        )
        heartbeat_thread.start()

    def stop_heartbeat() -> None:
        heartbeat_stop.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=1)

    try:
        yield
    except Exception as exc:
        stop_heartbeat()
        upstream_status = getattr(exc, "status_code", None)
        if not isinstance(upstream_status, int):
            upstream_status = getattr(
                getattr(exc, "response", None),
                "status_code",
                None,
            )
        logger.error(
            "request_id=%s stage=%s event=failed error_type=%s "
            "upstream_status=%s elapsed_ms=%.1f%s",
            request_id,
            stage,
            type(exc).__name__,
            upstream_status,
            (perf_counter() - started_at) * 1000,
            _format_fields(fields),
        )
        raise
    else:
        stop_heartbeat()
        logger.info(
            "request_id=%s stage=%s event=completed elapsed_ms=%.1f%s",
            request_id,
            stage,
            (perf_counter() - started_at) * 1000,
            _format_fields(fields),
        )


def log_event(
    logger: logging.Logger,
    stage: str,
    event: str,
    **fields: object,
) -> None:
    logger.info(
        "request_id=%s stage=%s event=%s%s",
        request_id_context.get(),
        stage,
        event,
        _format_fields(fields),
    )
