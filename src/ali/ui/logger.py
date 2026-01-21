# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Loggers are used for modules to log important messages.

Important:
Some logs are used by the gradio gui app to display some results.
The format of the log is important.
"""

import logging
from logging import handlers  # noqa: F401
from pathlib import Path
from queue import Queue

DEFAULT_LOG_DIR = Path("_logs")
WRITE_MODE = "w+"  # File write mode. Usually 'a' or 'w+'
CONSOLE_LEVEL = logging.INFO  # console logging level


def get_custom_logger(
    name: str = "main",
    dir_: Path = DEFAULT_LOG_DIR,
    console_level: int = CONSOLE_LEVEL,
) -> logging.Logger:
    """Create a logger.

    Important:
    Some logs are used by the gradio gui app to display some results.
    The format of the log is important.

    Args:
        name (str, optional): Logger name. Defaults to "main".
        dir_ (Path, optional): directory where to store the log.
            Defaults to DEFAULT_LOG_DIR.
        console_level (int, optional): Logging.level. Defaults to CONSOLE_LEVEL.

    Raises:
        TypeError: Raised if some parameters are of wrong type.
        FileNotFoundError: Raised if dir_ is not found.

    Returns:
        logging.Logger: created logger
    """
    # Create log dir
    if not isinstance(dir_, (Path, str)):
        raise TypeError(f"param `dir` must be Path or str, not {type(dir_)}")
    dir_ = Path(dir_)
    if not dir_.parent.exists():
        raise FileNotFoundError(f"Directory does not exist: {dir_.parent}.")
    dir_.mkdir(exist_ok=True)

    logger = logging.getLogger(name=name)

    logger.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter("%(message)s")

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # create rotating file handler
    log_file_path = DEFAULT_LOG_DIR / f"ali_{name}.log"
    fh = logging.FileHandler(str(log_file_path), WRITE_MODE)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Adding messages to queue for gradio app
    que: Queue = Queue(100)
    qh = logging.handlers.QueueHandler(que)
    qh.setLevel(logging.DEBUG)
    qh.setFormatter(formatter)
    logger.addHandler(qh)

    if WRITE_MODE == "a":
        with fh._open() as f:
            f.write("\n\n" + "#" * 20 + " Log start " + "#" * 20 + "\n\n")

    return logger


LOGGER_MAIN = get_custom_logger("main", console_level=logging.INFO)

LOGGER_CD = get_custom_logger("RADAR-CD")
LOGGER_CR = get_custom_logger("DATCO-CR")
LOGGER_ALI = get_custom_logger("ALI")
LOGGER_CLEARANCES = get_custom_logger("DATCO-CLEARANCES")
LOGGER_LLM = get_custom_logger("LLM")
