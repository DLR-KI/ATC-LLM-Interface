# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Dataset generation.

Dataset columns:
['id', 'solution_1', 'solution_2', 'policy', 'acceptable_solutions', 'explanation'].

- id: unique id for this data point
- solution_1: first Conflict Resolution solution
- solution_2: second Conflict Resolution solution
- policy: list of rules
- acceptable solution: [0-3]
   - 0: none of the solutions fulfil the policy.
   - 1: first solution is the only acceptable solution
   - 2: second solution is the only acceptable solution
   - 3: both solutions are acceptable

Format jsonl
"""

import json
import operator
import random
import string
import typing
from pathlib import Path

from ali.solver.command import AltitudeCommand, HeadingCommand, SpeedCommand
from ali.solver.resolution import Solution

FILE_PATH = Path(__file__).parent / "dataset.jsonl"

HEADERS = [
    "id",
    "solution_1",
    "solution_2",
    "policy",
    "acceptable_solutions",
    "explanation",
]


def generate_solutions(
    n_solutions: int = 100,
    max_n_commands: int = 5,
) -> tuple[list[Solution], list[Solution]]:
    """Make two lists of solutions.

    Args:
        n_solutions (int, optional): How many solutions to generate. Defaults to 100.
        max_n_commands (int, optional): max number of command per solution.
            Defaults to 5.

    Raises:
        ValueError: Raises error if wrong data is about to be generated.
            It should not happen.

    Returns:
        tuple[list[Solution], list[Solution]]: A list of unique solutions
            and a second list being a shuffle of the first one.
    """
    solutions_1 = []

    for i in range(n_solutions):
        solution = Solution()

        solution.callsign = "".join(
            [random.choice(string.ascii_uppercase) for i in range(3)]
            + [str(random.randint(0, 9)) for i in range(3)],
        )
        solution.commands = []

        for _n_command in range(random.randint(1, max_n_commands)):
            command_type = i % 3

            if command_type == 0:
                # generating headings
                params = {
                    "time": random.randint(
                        0,
                        3600 * 24 - 1,
                    ),  # between 0 and 23:59:59 hours (sec)
                    "value": random.randint(0, 360),  # (deg)
                }
                solution.commands.append(HeadingCommand(**params))
            elif command_type == 1:
                # generating Altitude
                params = {
                    "time": random.randint(
                        0,
                        3600 * 24 - 1,
                    ),  # between 0 and 23:59:59 hours (sec)
                    "value": random.randint(1, 20) * 600,  # typical flight levels (m)
                }
                solution.commands.append(AltitudeCommand(**params))
            elif command_type == 2:
                # generating speed command
                params = {
                    "time": random.randint(
                        0,
                        3600 * 24 - 1,
                    ),  # between 0 and 23:59:59 hours (sec)
                    "value": random.randint(180, 260),  # some realistic speeds (m/s)
                }
                solution.commands.append(SpeedCommand(**params))
            else:
                raise ValueError(
                    f"Command type not supported. \
                                 `{command_type}` not in [0,2]"
                )
        solutions_1.append(solution)

    solutions_2 = solutions_1.copy()
    random.shuffle(solutions_2)
    return solutions_1, solutions_2


def write_data(
    file: typing.TextIO,
    solution_1: Solution,
    solution_2: Solution,
    sorting_rules: dict,
    valid_solutions: int,
    explanation: str,
) -> None:
    """Writing generated data into file.

    Args:
        file (typing.TextIO): file handler.
        solution_1 (Solution): cf. script doc.
        solution_2 (Solution): cf. script doc.
        sorting_rules (dict): cf. script doc.
        valid_solutions (int): cf. script doc.
        explanation (str): cf. script doc.
    """
    data = [
        solution_1.to_json(),
        solution_2.to_json(),
        sorting_rules,
        valid_solutions,
        explanation,
    ]
    data = [hex(hash(str(data))).upper()[-6:], *data]  # adding unique ID
    file.write(json.dumps(data) + "\n")


def make(  # noqa: C901
    file_path: Path = FILE_PATH,
    n_solutions: int = 100,
    max_n_commands: int = 5,
) -> None:
    """Generate a dataset.

    Args:
        file_path (Path, optional): Destination path for dataset. Defaults to FILE_PATH.
        n_solutions (int, optional): number of unique solution to generate.
            Defaults to 100.
        max_n_commands (int, optional): max number of commands per solution.
            Defaults to 5.

    Raises:
        ValueError: Raises error if wrong data is about to be generated.
            It should not happen.
    """
    solutions_1, solutions_2 = generate_solutions(n_solutions, max_n_commands)

    with file_path.open("w", encoding="utf-8") as file:
        file.write(json.dumps(HEADERS) + "\n")
        """First batch of data."""
        sorting_rules_synonyms = [
            {
                "G1": "Prefer a solution which does not involve a change of altitude.",
            },
        ]

        for sorting_rules in sorting_rules_synonyms:
            for s1, s2 in zip(solutions_1, solutions_2, strict=False):
                s_i_is_valid = [True, True]
                explanation = ""

                for idx, s in enumerate([s1, s2]):
                    s_idx = idx + 1  # solutions are numbered 1,2 not 0,1
                    for c in s.commands:
                        if isinstance(c, AltitudeCommand):
                            s_i_is_valid[idx] = False
                            if f"Solution {s_idx}" not in explanation:
                                explanation += f"Solution {s_idx} involves a change \
                                    of altitude which is not preferred by rule G1. "

                valid_solutions = (
                    s_i_is_valid[0] + 2 * s_i_is_valid[1]
                )  # "binary addition" of valid solutions. See header.
                if valid_solutions == 3:
                    explanation += "Both solutions satisfy the the rules equally. "

                write_data(file, s1, s2, sorting_rules, valid_solutions, explanation)

        # New batch of data
        sorting_rules_synonyms = [
            {
                "G1": "Prefer a solution which does not involve a change of speed.",
            },
        ]

        for sorting_rules in sorting_rules_synonyms:
            for s1, s2 in zip(solutions_1, solutions_2, strict=False):
                s_i_is_valid = [True, True]
                explanation = ""

                for idx, s in enumerate([s1, s2]):
                    s_idx = idx + 1  # solutions are numbered 1,2 not 0,1
                    for c in s.commands:
                        if isinstance(c, SpeedCommand):
                            s_i_is_valid[idx] = False
                            if f"Solution {s_idx}" not in explanation:
                                explanation += f"Solution {s_idx} involves a change \
                                    of speed which is not preferred by rule G1. "

                valid_solutions = (
                    s_i_is_valid[0] + 2 * s_i_is_valid[1]
                )  # "binary addition" of valid solutions. See header.
                if valid_solutions == 3:
                    explanation += "Both solutions satisfy the the rules equally. "

                write_data(file, s1, s2, sorting_rules, valid_solutions, explanation)

        # New batch of data
        sorting_rules_synonyms = [
            {
                "G1": "Prefer a solution which does not involve a change of heading.",
            },
        ]

        for sorting_rules in sorting_rules_synonyms:
            for s1, s2 in zip(solutions_1, solutions_2, strict=False):
                s_i_is_valid = [True, True]
                explanation = ""

                for idx, s in enumerate([s1, s2]):
                    s_idx = idx + 1  # solutions are numbered 1,2 not 0,1
                    for c in s.commands:
                        if isinstance(c, HeadingCommand):
                            s_i_is_valid[idx] = False
                            if f"Solution {s_idx}" not in explanation:
                                explanation += f"Solution {s_idx} involves a change \
                                    of heading which is not preferred by rule G1. "

                valid_solutions = (
                    s_i_is_valid[0] + 2 * s_i_is_valid[1]
                )  # "binary addition" of valid solutions. See header.
                if valid_solutions == 3:
                    explanation += "Both solutions satisfy the the rules equally. "

                write_data(file, s1, s2, sorting_rules, valid_solutions, explanation)

        # New batch of data
        sorting_rules_synonyms = [
            {
                "G1": "Prefer a solution which includes only heading commands.",
            },
            {
                "G1": "Prefer a solution which includes only changes of heading.",
            },
        ]

        for sorting_rules in sorting_rules_synonyms:
            for s1, s2 in zip(solutions_1, solutions_2, strict=False):
                s_i_is_valid = [True, True]
                explanation = ""

                for idx, s in enumerate([s1, s2]):
                    s_idx = idx + 1  # solutions are numbered 1,2 not 0,1
                    for c in s.commands:
                        if not isinstance(c, HeadingCommand):
                            s_i_is_valid[idx] = False
                            if f"Solution {s_idx}" not in explanation:
                                cmd_type = None
                                if isinstance(c, AltitudeCommand):
                                    cmd_type = "altitude"
                                elif isinstance(c, SpeedCommand):
                                    "speed"
                                else:
                                    raise ValueError(
                                        f"command {c} has unexpected type: {type(c)}"
                                    )
                                explanation += f"Solution {s_idx} involves a change of \
                                {cmd_type} which is not preferred by rule G1. "

                valid_solutions = (
                    s_i_is_valid[0] + 2 * s_i_is_valid[1]
                )  # "binary addition" of valid solutions. See header.
                if valid_solutions == 3:
                    explanation += "Both solutions satisfy the the rules equally. "

                write_data(file, s1, s2, sorting_rules, valid_solutions, explanation)

        # New batch of data
        sorting_rules_synonyms = [
            {
                "G1": "Prefer a solution which includes at least one heading commands.",
            },
            {
                "G1": "Prefer a solution which includes at least one change of "
                "heading.",
            },
        ]

        for sorting_rules in sorting_rules_synonyms:
            for s1, s2 in zip(solutions_1, solutions_2, strict=False):
                s_i_is_valid = [False, False]
                explanation = ""

                for idx, s in enumerate([s1, s2]):
                    s_idx = idx + 1  # solutions are numbered 1,2 not 0,1
                    for c in s.commands:
                        if isinstance(c, HeadingCommand):
                            s_i_is_valid[idx] = True

                valid_solutions = (
                    s_i_is_valid[0] + 2 * s_i_is_valid[1]
                )  # "binary addition" of valid solutions. See header.
                if valid_solutions == 0:
                    explanation += "None of the solutions include at least one heading "
                    "command, as preferred by rule G1. "
                elif valid_solutions == 1:
                    explanation += "Solution 1 includes at least one heading command "
                    "as preferred by rule G1, but solution 2 does not."
                if valid_solutions == 2:
                    explanation += "Solution 2 includes at least one heading command "
                    "as preferred by rule G1, but solution 1 does not."
                if valid_solutions == 3:
                    explanation += "Both solutions satisfy the the rule G1 equally. "

                write_data(file, s1, s2, sorting_rules, valid_solutions, explanation)


def load(file_path: Path = FILE_PATH) -> tuple[list, list]:
    """Read and return the dataset.

    Args:
        file_path (Path, optional): path of the dataset. Defaults to FILE_PATH.

    Returns:
        header: the list of the columns names
        dataset: the list of data points
    """
    dataset = []
    with file_path.open("r", encoding="utf-8") as file:
        line = file.readline()
        header = json.loads(line)

        for line in file.readlines():
            data = json.loads(line)
            # id, solution_raw, policy, violation, explanation = data
            dataset.append(data)

    print(f"Dataset loaded. Size: {len(dataset)}")

    return header, dataset


def analyse_dataset(headers: list, dataset: list, plot: bool = True) -> None:
    """Display a simple analysis of the distribution of the dataset.

    Args:
        headers (list): name of the columns
        dataset (list): list of data points
        plot (bool): whether to display the plots or not.
    """
    import matplotlib.pyplot as plt
    import pandas as pd

    df = pd.DataFrame(data=dataset, columns=headers)

    print("Head: \n")
    print(df.head())

    df["commands"] = df["solution_1"].apply(operator.itemgetter("commands"))
    df["n_commands"] = df["commands"].apply(len)
    df["n_rules"] = df["policy"].apply(len)

    print("\nUnique: \n")
    print(
        df.drop(columns=["solution_1", "solution_2", "acceptable_solutions"])
        .astype(str)
        .nunique()
    )

    print("\nValue count: ")
    print(
        df["acceptable_solutions"]
        .value_counts(normalize=True)
        .mul(100)
        .round(1)
        .astype(str)
        + " %"
    )
    for c in ["n_commands", "n_rules"]:
        print(
            pd.concat(
                [
                    df[c].value_counts(),
                    df[c].value_counts(normalize=True).mul(100).round(1).astype(str)
                    + " %",
                ],
                axis=1,
            )
        )

    if plot:
        df[["acceptable_solutions", "n_commands", "n_rules"]].astype(int).hist()
        # df[['acceptable_solutions', 'n_commands', 'n_rules']].plot.hist(subplots=True)
        plt.show()

    # print('\nFinal frame:\n')
    # print(df.drop(columns=['solution', 'explanation']))


if __name__ == "__main__":
    make(n_solutions=2)
    headers, ds = load()
    analyse_dataset(headers, ds)
