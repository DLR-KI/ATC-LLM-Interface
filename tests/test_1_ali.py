# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Testing ATC alignment methods."""

from pathlib import Path

from ali.alignment import llm
from ali.alignment.filtering import filter_solutions
from ali.alignment.policy import ATCPolicy
from ali.alignment.sorting import get_best_solution
from ali.solver.command import AltitudeCommand, HeadingCommand, SpeedCommand
from ali.solver.resolution import Solution

POLICY_PATH = Path(__file__).parent / "atco-policy.json"
policy = ATCPolicy(POLICY_PATH)


llm.CLIENT = llm.MockedClient()


def generate_solutions() -> list[Solution]:
    solutions_list = [
        Solution(
            callsign="ABC123",
            commands=[
                AltitudeCommand(time=1000, value=5000),
                SpeedCommand(time=1000, value=5000),
                HeadingCommand(time=1000, value=5000),
            ],
        ),
        Solution(
            callsign="DEF123",
            commands=[AltitudeCommand(time=1000, value=5000)],
        ),
        Solution(
            callsign="GHI123",
            commands=[
                HeadingCommand(time=1000, value=5000),
            ],
        ),
    ]
    return solutions_list


def test_filter():
    """Test if the filtering pipeline works (including call to llm api).

    Does not test if the answer is correct.
    """
    llm.CLIENT.answer = """
```json
{
    "Explanation": " ",
    "Answer": "no"
}
```
"""
    solutions_list = generate_solutions()
    valid_solutions = filter_solutions(policy=policy, solutions=solutions_list)

    assert len(valid_solutions) > 0, (
        "Filtering failed. `filter` returned an empty list."
    )


def test_sort():
    """Test if the sorting pipeline works (including call to llm api).

    Does not test if the answer is correct.
    """
    llm.CLIENT.answer = """
```json
{
    "Explanation": " ",
    "Answer": "Solution 1"
}
```
"""
    solutions_list = generate_solutions()
    best_solution = get_best_solution(solutions=solutions_list, policy=policy)

    assert isinstance(best_solution, Solution)
