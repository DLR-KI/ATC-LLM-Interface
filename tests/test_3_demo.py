# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Testing ALI demo."""

import logging
from pathlib import Path

import pytest

from ali import ali


def test_demo(caplog: pytest.LogCaptureFixture):
    """Test if the ali demo is running on a basic scenario.

    It does not check if the results are correct.

    Raises:
        AssertionError: when the demo does not run until the end.
    """
    bs_scn_path = Path(__file__).parent / "bs_scenario.scn"

    with caplog.at_level(logging.DEBUG):
        ali.main(bs_scn_path=bs_scn_path, gui=False)

        # check that something was logged.
        assert len(caplog.record_tuples) > 0, (
            "Nothing was logged. Probably the demo did not run at all, "
            + "or the loggers were modified."
        )

        # Check that the demo reached the end: best solution execution.
        for log_entry in reversed(caplog.record_tuples):
            if (
                log_entry[0] == "ALI"
                and "# Best solution to be executed" in log_entry[2]
            ):
                # the demo reached the execution of the best solution.
                break
        else:
            raise AssertionError(
                "The demo did not run until the end, until solution execution."
            )
