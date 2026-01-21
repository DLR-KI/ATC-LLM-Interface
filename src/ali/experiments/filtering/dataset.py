# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Dataset generation.

Dataset columns:
['id', 'solution', 'policy', 'violation', 'explanation'].

- id: unique id for this data point
- solution: Conflict Resolution solution
- policy: list of rules
- violation: whether or not the solution violates the policy
- a short explanation why there is violation or not.

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
DOC_PATH = FILE_PATH.with_suffix(".txt")

HEADERS = ["id", "solution", "policy", "violation", "explanation"]


def generate_solutions(
    n_solutions: int = 100,
    max_n_commands: int = 5,
) -> list[Solution]:
    """Make a list of solutions.

    Args:
        n_solutions (int, optional): How many solutions to generate. Defaults to 100.
        max_n_commands (int, optional): max number of command per solution.
            Defaults to 5.

    Raises:
        ValueError: Raises error if wrong data is about to be generated.
            It should not happen.

    Returns:
        list[Solution]: A list of unique solutions.
    """
    solutions = []

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

        solutions.append(solution)
    return solutions


def write_data(
    file: typing.TextIO,
    solution: Solution,
    filtering_rules: dict,
    violation: bool,
    explanation: str,
) -> None:
    """Writing generated data into file.

    Args:
        file (typing.TextIO): file handler.
        solution (Solution): solution.
        filtering_rules (dict): policy.
        violation (bool): violation.
        explanation (str): explanation.
    """
    data = [solution.to_json(), filtering_rules, violation, explanation]
    data = [hex(hash(str(data))).upper()[-6:], *data]
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
    """
    solutions = generate_solutions(n_solutions, max_n_commands)

    with file_path.open("w", encoding="utf-8") as file:
        file.write(json.dumps(HEADERS) + "\n")
        """First batch of data."""
        filtering_rules_synonyms = [
            {
                "F1": "Do not use a command involving a change of speed.",
                "F2": "Do not use a command involving a change of altitude.",
            },
            {
                "F1": "It is forbidden to use a command involving a change of speed.",
                "F2": "It is forbidden use a command involving a change of altitude.",
            },
        ]

        for filtering_rules in filtering_rules_synonyms:
            for s in solutions:
                violation = False
                explanation = ""

                for c in s.commands:
                    if isinstance(c, SpeedCommand):
                        violation = True
                        if "F1" not in explanation:
                            explanation += "The solution violates rule F1, \
                                as it includes a change of speed."
                    if isinstance(c, AltitudeCommand):
                        violation = True
                        if "F2" not in explanation:
                            explanation += "The solution violates rule F2, \
                                as it includes a change of altitude."
                if not violation:
                    explanation = "The solution is not violating any of the rules \
                        as it does not change either the speed or the altitude."

                write_data(file, s, filtering_rules, violation, explanation)

        # New batch of data
        filtering_rules_synonyms = [
            {
                "F1": "Only use a command involving a change of heading.",
            },
            {
                "F1": "Do not use a command with either a change of altitude \
                    nor speed.",
            },
        ]

        for filtering_rules in filtering_rules_synonyms:
            for s in solutions:
                violation = False
                explanation = ""

                for c in s.commands:
                    if isinstance(c, SpeedCommand):
                        violation = True
                        if "speed" not in explanation:
                            explanation += "The solution violates rule F1, \
                                as it includes a change of speed."
                    if isinstance(c, AltitudeCommand):
                        violation = True
                        if "altitude" not in explanation:
                            explanation += "The solution violates rule F1, \
                                as it includes a change of altitude."
                if not violation:
                    explanation = "The solution is not violating any of the rules \
                        as it only changes the heading, and not the altitude \
                            nor the speed."

                write_data(file, s, filtering_rules, violation, explanation)

        # New batch of data
        filtering_rules_synonyms = [
            {
                "F1": "Do not use a command involving a change of heading.",
                "F2": "Do not use a command involving a change of altitude.",
            },
            {
                "F1": "It is forbidden to use a command involving a change of heading.",
                "F2": "It is forbidden to use a command involving a change of \
                    altitude.",
            },
        ]

        for filtering_rules in filtering_rules_synonyms:
            for s in solutions:
                violation = False
                explanation = ""

                for c in s.commands:
                    if isinstance(c, HeadingCommand):
                        violation = True
                        if "F1" not in explanation:
                            explanation += "The solution violates rule F1, \
                                as it includes a change of heading."
                    if isinstance(c, AltitudeCommand):
                        violation = True
                        if "F2" not in explanation:
                            explanation += "The solution violates rule F2, \
                                as it includes a change of altitude."
                if not violation:
                    explanation = "The solution is not violating any of the rules \
                        as it does not change either the heading or the altitude."

                write_data(file, s, filtering_rules, violation, explanation)


def load(file_path: Path = FILE_PATH) -> tuple[list, list]:
    """Read and return the dataset.

    Args:
        file_path (Path, optional): path of the dataset. Defaults to FILE_PATH.

    Returns:
        header: the list of the columns names.
        dataset: the list of data points.
    """
    dataset = []
    print(file_path)
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

    df["commands"] = df["solution"].apply(operator.itemgetter("commands"))
    df["n_commands"] = df["commands"].apply(len)
    df["n_rules"] = df["policy"].apply(len)

    print("\nUnique: \n")
    print(df.drop(columns=["solution", "violation"]).astype(str).nunique())

    print("\nValue count: ")
    print(
        df["violation"].value_counts(normalize=True).mul(100).round(1).astype(str)
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
        df[["violation", "n_commands", "n_rules"]].astype(int).hist()
        # df[['violation', 'n_commands', 'n_rules']].plot.hist(subplots=True)
        plt.show()


if __name__ == "__main__":
    make(n_solutions=2, max_n_commands=5)
    headers, ds = load()
    analyse_dataset(headers, ds)
