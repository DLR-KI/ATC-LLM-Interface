# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Sorting solutions based on ATC policy.

The CONTEXT is given to the chat model with role 'system'. Facts were
useful to avoid the model guessing stuff like "a change of heading may
change the speed", resulting in wrong filtering.

The PROMPT is give to the chat model with role 'user'. It includes the
task the model has to solve and the format of the answer. The answer is
a JSON, which can be parsed to extract 1. the answer 2. the explanation.
"""

import json

from ollama import Message

from ali.alignment import llm
from ali.alignment.policy import ATCPolicy
from ali.alignment.utils import InvalidAnswerError, answer_parser
from ali.solver.resolution import Solution
from ali.ui.logger import LOGGER_ALI

MAX_RETRIES = 3


class SortingFailureError(Exception):
    """Raised when sorting fails."""


CONTEXT = """
You are an assistant to an Air Traffic Controller.

Do not guess. Only use the facts.

# Facts
- The "heading" command changes the direction of the aircraft. \
    "heading" does not modify the speed nor the altitude.
- The "climb" command changes the altitude of the aircraft. \
    "climb" does not modify the speed nor the direction.
- The "speed" command changes the speed of the aircraft. \
    "speed" does not modify the altitude nor the direction.

# Core rules
{policy}
"""

SORTING_PROMPT = """
You will encounter some core rules that you need to always satisfy when choosing the \
    correct solutions for the ATCO.
The rules express preference over different options.
The order of the rules does matter.
Always try to satisfy the first rule. If the first rule is not applicable, \
    use the second.

# Solution 1
```json
{solution_1}
```

# Solution 2
```json
{solution_2}
```

# Accepted answer format
```json
{
    "Explanation": "[One sentence explanation based on rules]",
    "Answer": "[Solution 1/Solution 2]"
}
```

It is required to always provide a definite answer (solution 1 or solution 2) \
    otherwise the program fails.
If both solutions are equal with respect to the core rules, \
    any of the two solutions can be chosen.

# Inquiry
Based on the core rules, which solution is preferred?

Answer the inquiry in JSON in code block.
"""

VALID_SORTING_ANSWERS = {"solution 1", "solution 2"}


def get_best_solution(solutions: list[Solution], policy: ATCPolicy) -> Solution:
    """Returns the best solution based on ATC Policy.

    Args:
        solutions (list[Solution]): List of solutions to sort from
        policy (ATCPolicy): ATC Policy containing "sorting policy"

    Raises:
        Exception: The list of solutions cannot be empty.
        SortingFailureError: LLM failed to return a valid answer.

    Returns:
        Solution: The one best solution.
    """
    assert isinstance(solutions, list), (
        f"Argument `solutions` must be a list, not: {type(solutions)}"
    )
    for s in solutions:
        assert isinstance(s, Solution), (
            f"Argument `solutions` must contain `Solution` values only. Not: {type(s)}"
        )

    if len(solutions) == 0:
        raise Exception("Received empty list of solutions.")

    if len(solutions) == 1:
        LOGGER_ALI.debug(f"Only one solution is accepted: \n{solutions[-1]!s}")
        return solutions[-1]

    # Getting sorting rules
    sorting_rules = policy.sorting_rules

    # Preparing CONTEXT
    context = CONTEXT.replace(
        "{policy}",  # noqa: RUF027
        "\n".join([f"{rule.id}: {rule.value}" for rule in sorting_rules]),
    )
    LOGGER_ALI.debug("# System context")
    LOGGER_ALI.debug("\n" + context)

    # Sorting strategy: always comparing first with last solution,
    # the worst is dropped from the solutions list.
    failed_attempts = 0
    while len(solutions) > 1:  # Last solutions in solution list -> best one.
        s1, s2 = (
            solutions[0],
            solutions[-1],
        )  # comparing first solution with the last one.
        # LOGGER_ALI.debug("## Sorting pair of solutions" )
        prompt = SORTING_PROMPT.replace(
            "{solution_1}",
            json.dumps(s1.commands_to_json(), indent=4, default=str),
        )
        prompt = prompt.replace(
            "{solution_2}",
            json.dumps(s2.commands_to_json(), indent=4, default=str),
        )

        messages = [
            Message(role="system", content=context),
            Message(role="user", content=prompt),
        ]

        LOGGER_ALI.debug("\n### LLM PROMPT \n" + prompt)
        response = llm.chat(messages=messages, options=llm.ollama_options)["sequences"][
            0
        ]
        LOGGER_ALI.debug("\n### LLM ANSWER \n" + response)

        try:
            preference, _ = answer_parser(response, VALID_SORTING_ANSWERS)
        except InvalidAnswerError as exc:
            failed_attempts += 1
            if failed_attempts > MAX_RETRIES:
                raise SortingFailureError from exc
            continue  # Let's try one more time

        preferred_solution = 1 if preference == "solution 1" else 2

        solutions = solutions[:-1] if preferred_solution == 1 else solutions[1:]

    # LOGGER_ALI.debug("# Preferred Solution" )
    # LOGGER_ALI.debug("\n" + str(solutions[-1]) )

    return solutions[-1]
