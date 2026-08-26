"""Shared test fixtures."""
import logging

import pytest

from amigarig.log import logger, set_verbosity


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def log_messages():
    """Captures amigarig.log.logger output as a plain list of rendered
    messages, independent of its StreamHandler's stream (which capsys
    can't see -- it caches sys.stderr at handler-construction time) and
    of caplog's level-forcing (which would defeat testing "not verbose
    logs nothing"). Resets verbosity to 0 (WARNING) on teardown."""
    handler = _ListHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield handler.messages
    finally:
        logger.removeHandler(handler)
        set_verbosity(0)
