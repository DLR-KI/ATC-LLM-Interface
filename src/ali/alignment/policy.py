# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Loading and interpreting the ATC Policies."""

import json
from pathlib import Path


class Rule:
    """A rule to be added to the ATC policy.

    A rule is formulated in natural language.
    """

    def __init__(self, idx: int, value: str) -> None:
        self.id = idx
        self.value = value

    def __str__(self) -> str:
        return f"{self.id} = {self.value} "


class ATCPolicy:
    """A collection of rules to be followed when performing CR."""

    def __init__(self, file_path: Path | None = None) -> None:
        self.filtering_rules: list[Rule] = []
        self.sorting_rules: list[Rule] = []

        if file_path is not None:
            assert isinstance(file_path, Path)
            assert file_path.exists()

            self.parse_json(file_path)

    def parse_json(self, json_file: Path | str) -> None:
        """Parse policy given as JSON.

        Args:
            json_file (Path | str): Path to JSON file with ATC Policy.
        """
        contents = Path(json_file).read_text(encoding="utf-8")

        data = json.loads(contents)
        for key, value in data.items():
            if key == "FILTERING_RULES":
                for v in value:
                    self.filtering_rules.append(
                        Rule(next(iter(v.keys())), next(iter(v.values()))),
                    )
            elif key == "SORTING_RULES":
                for v in value:
                    self.sorting_rules.append(
                        Rule(next(iter(v.keys())), next(iter(v.values()))),
                    )

    def print_rules(self) -> None:
        """Print rules in console."""
        print("FILTERING RULES: ")
        for rule in self.filtering_rules:
            print(rule)
        print("\nSORTING RULES: ")
        for rule in self.sorting_rules:
            print(rule)
