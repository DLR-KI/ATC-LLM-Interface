# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Filters solutions based on ATC policy.

The CONTEXT is given to the chat model with role 'system'.
Facts were useful to avoid the model guessing stuff like "a change of
heading may change the speed", resulting in wrong filtering.

The PROMPT is give to the chat model with role 'user'.
It includes the task the model has to solve and the format of the
answer. The answer is a JSON, which can be parsed to extract 1. the
answer 2. the explanation.

!!! Very important result: the explanation must be before the answer.
   - with the explanation before, we leverage the "chain of thoughts"
    idea.
   - with the answer before, the answer is more likely to be wrong
    (because no space given for "thoughts"),
    and when the answer is wrong, the model will try to explain a wrong
    answer, which it will! Resulting in hallucinations and false logic.
"""

import json

from ollama import Message

from ali.alignment import llm
from ali.alignment.policy import ATCPolicy
from ali.alignment.utils import InvalidAnswerError, answer_parser
from ali.solver.resolution import Solution
from ali.ui.logger import LOGGER_ALI


class FilteringFailureError(Exception):
    """Raised when filtering fails."""


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
"""

FILTER_PROMPT = """
You need to make sure that no core rule is violated by the following solution.

# Solution
```json
{solution}
```

# Core rules
{policy}

# Answer format
```json
{
    "Explanation": "[One sentence explanation based on rules and solution]",
    "Answer": "[yes/no]"
}
```

# Inquiry
Does the provided solution violate one of the core rules?

Answer the inquiry in JSON in code block.
"""

VALID_FILTERING_ANSWERS = {"yes", "no"}


def filter_solutions(
    solutions: list[Solution],
    policy: ATCPolicy,
    ground_truth: list[bool] | None = None,
) -> list[Solution]:
    """Filters solutions based on ATC policy.

    Filters the solutions that do not fit the ATC Policy (i.e. invalid solutions).
    Returns only the list of valid solutions. The solutions are unmodified.

    Args:
        solutions (list[Solution]): list of CR solutions
        policy (ATCPolicy): policy containing rules on how to solve a conflict
        ground_truth (list[bool], optional): Providing ground truth is used in testing.\
            If the answer does not correspond to the truth, an error is raised.\
                Defaults to None.

    Raises:
        InvalidAnswerError: Raised if answer given by LLM is not correctly formatted.
        ValueError: Raised if answer does not correspond to ground truth.

    Returns:
        list[Solution]: Returns the list of valid solutions.
    """
    filtering_rules = policy.filtering_rules

    # Preparing CONTEXT
    context = CONTEXT
    LOGGER_ALI.debug("# System context")
    LOGGER_ALI.debug("\n" + context)

    valid_solutions = []
    keep_mask = []  # for debug only

    # Solutions are filtered one by one.
    for s in solutions:
        # LOGGER_ALI.debug("## Filtering individual solution" )
        prompt = FILTER_PROMPT.replace(
            "{solution}",
            json.dumps(s.commands_to_json(), indent=4, default=str),
        )
        prompt = prompt.replace(
            "{policy}",  # noqa: RUF027
            "\n".join([f"{rule.id}: {rule.value}" for rule in filtering_rules]),
        )

        messages = [
            Message(role="system", content=context),
            Message(role="user", content=prompt),
        ]

        LOGGER_ALI.debug("\n### LLM PROMPT\n" + prompt)
        response = llm.chat(messages=messages, options=llm.ollama_options)["sequences"][
            0
        ]
        LOGGER_ALI.debug("\n### LLM ANSWER \n" + response)

        violation, _explanation = answer_parser(response, VALID_FILTERING_ANSWERS)
        if violation == "yes":
            # if a rule is violated, the solution is not kept
            keep = False
        elif violation == "no":
            keep = True
            valid_solutions.append(s)
        else:
            # Should never happen, since answer_parser already check valid answers.
            raise InvalidAnswerError(f"Not a valid answer: {violation}")

        keep_mask.append(keep)

    success = True
    if ground_truth:
        success = all(keep_mask[i] == ground_truth[i] for i in range(len(solutions)))
    if not success:
        raise ValueError("Filtering unsuccessful")

    return valid_solutions
