import logging
import time

from app.logging_utils import log_stage


def test_log_stage_emits_heartbeat_during_long_running_stage(
    caplog,
) -> None:
    logger = logging.getLogger("app.test_logging")
    with caplog.at_level(logging.INFO, logger="app"):
        with log_stage(
            logger,
            "llm.request",
            heartbeat_interval_seconds=0.01,
            provider="test-provider",
        ):
            time.sleep(0.035)

    assert "stage=llm.request event=started" in caplog.text
    assert "stage=llm.request event=still_running elapsed_ms=" in caplog.text
    assert "stage=llm.request event=completed elapsed_ms=" in caplog.text
