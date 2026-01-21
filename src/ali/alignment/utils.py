# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Helping functions for ali."""

import contextlib
import json
import re


class InvalidAnswerError(Exception):
    """Raised when the answer from the model is invalid."""


class Bcolors:
    """Colors for printing in console."""

    # ANSI escape codes: https://en.wikipedia.org/wiki/ANSI_escape_code
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    GRAY = "\033[38;5;248m"
    DARK_BLUE = "\033[38;5;12m"
    GREEN_BACK = "\033[48;5;154m"


answer_pattern = re.compile(
    r"""
(?P<answer>   # catch the answer group
{             # the group starts with one bracket
[^{]+         # then, we can match anything but an opening bracket
}             # there is one closing bracket
)             # the action group is complete
""",
    re.VERBOSE,
)


def answer_parser(text: str, valid_answers: set) -> tuple[str, str]:
    """Parse the answer from the model.

    Parse the answer from the model (json) and extract:
    1. the answer
    2. the explanation

    To be valid:
    - The text must contain a valid json
    - the json must contain the key: `answer`
    - the value of `answer` must be an element of `valid_answers`

    If no explanation provided, an empty string is returned as
        explanation.

    Args:
        text (str): json answer from model
        valid_answers (set): a set with all valid answers. Valid answers
            must be lower characters.

    Raises:
        InvalidAnswerError: If the given text is not a valid json, the json
            does not contain the key `Answer`, or the `Answer` value is
            not in the `valid_answers` set (case insensitive).

    Returns:
        (str, str): answer, explanation
    """
    assert isinstance(text, str)
    assert isinstance(valid_answers, set)
    for x in valid_answers:
        assert str(x) == str(x).lower(), (
            f"valid answers must be lower characters. `{x}` is not valid."
        )

    answer = None
    explanation = ""

    m = re.search(answer_pattern, text.replace("\n", ""))
    if m is not None:
        j = None
        with contextlib.suppress(json.decoder.JSONDecodeError):
            j = json.loads(m.group("answer"))

        if j is None:
            raise InvalidAnswerError(f"Answer could not be parsed as JSON: {answer}")

        if j.get("Answer") is None:
            raise InvalidAnswerError(f"No answer found in: {j}")
        clean_answer = str(j["Answer"]).lower().strip()

        if clean_answer in valid_answers:
            answer = clean_answer
        else:
            raise InvalidAnswerError(f"Answer is invalid: {j['Answer']}")

        if j.get("Explanation") is None:
            pass

        return answer, explanation
    raise InvalidAnswerError(f"Invalid answer: {text}")
