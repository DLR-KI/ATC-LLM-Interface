# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Conflict Resolution module."""

import json
from abc import ABC, abstractmethod
from collections import UserDict

from bluesky.stack.stackbase import Stack
from bluesky.traffic.traffic import Traffic

from ali.solver.command import (
    AltitudeCommand,
    CommandBase,
    HeadingCommand,
    SpeedCommand,
)
from ali.ui.logger import LOGGER_CLEARANCES, LOGGER_MAIN


class Conflict:
    """Contains relevant information about a detected conflict.

    Args:
        callsigns (set): callsigns of two aircraft on conflicting routes.
        dcpa (float): Horizontal distance to CPA.
        tcpa (float): Time to CPA.
    """

    def __init__(self, callsigns: set, dcpa: float, tcpa: float) -> None:
        self.callsigns = callsigns
        self.dcpa = dcpa
        self.tcpa = tcpa

    def __repr__(self) -> str:
        return set(self.callsigns).__repr__()

    def __str__(self) -> str:
        return set(self.callsigns).__str__()

    def __eq__(self, value: object) -> bool:
        assert isinstance(value, Conflict), (
            f"Conflict can only be compared with Conflict, not: {type(value)}"
        )
        return self.callsigns == value.callsigns

    def __hash__(self) -> int:
        return hash(self.__repr__())


class Solution:
    """A dict with the information about a solution to a conflict.

    It contains:
    - the callsign of the aircraft to contact
    - the list of commands to send to this aircraft
    """

    callsign: str
    commands: list[CommandBase]

    def __init__(
        self, callsign: str = "", commands: list[CommandBase] | None = None
    ) -> None:
        self.callsign = callsign
        self.commands = commands or []

    def pretty_print(self) -> str:
        """Creates multiline indented json str to be printed.

        Returns:
            str:
        """
        pretty_solution = {
            "callsign": self.callsign,
            "commands": [
                {"time": str(c.time), "command": c.natural_command()}
                for c in self.commands
            ],
        }

        return str(json.dumps(pretty_solution, indent=4))

    def to_json(self) -> dict:
        """Convert to JSON serializable format.

        Returns:
            dict: JSON serializable object (and nested objects.)
        """
        return {
            "callsign": self.callsign,
            "commands": [c.to_json() for c in self.commands],
        }

    def commands_to_json(self) -> list:
        """List of of commands to JSON serializable format.

        Returns:
            list: JSON serializable object (and nested objects.)
        """
        return [c.to_json() for c in self.commands]

    def __repr__(self) -> str:
        return self.to_json().__repr__()

    """dot access dictionary attributes"""
    __getattr__ = UserDict.get


class SolverBase(ABC):
    """Abstract class for solver."""

    def __init__(self, stack: Stack) -> None:
        super().__init__()
        self.stack = stack

    @abstractmethod
    def resolve(
        self,
        conflict: Conflict,
        traf: list,
        current_time: int,
    ) -> list[Solution]:
        """Generates a list of solutions to solve the given conflict.

        Args:
            conflict (Conflict): conflict description.
            traf (list): Traffic information.
            current_time (int): current time.

        Returns:
            list[Solution]: The list of possible solutions to solve the conflict.
        """
        return [Solution()]

    def apply_solution(self, solution: Solution) -> None:
        """Apply a solution into BlueSky env.

        A solution is a list of commands to be added to the BlueSky
        stack.

        Args:
            solution (Solution): solution to be scheduled in the BlueSky stack.
        """
        for command in solution.commands:
            # Stack.scencmd.append(command.bluesky_command(solution.callsign))
            # Stack.scentime.append(command.time)
            self.stack(
                f"SCHEDULE {command.time}, "
                f"{command.bluesky_command(solution.callsign)}",
            )
            self.stack(
                f"ECHO SCHEDULE {command.time}, \
                    {command.bluesky_command(solution.callsign)}",
            )
            LOGGER_CLEARANCES.info(
                f"Scheduling task: {command.time} > \
                    {command.bluesky_command(solution.callsign)}",
            )


class DummySolver(SolverBase):
    """Dummy solver.

    The dummy solver provides some solutions which slightly change the course of
    one of the aircraft in conflict.

    DISCLAIMER:
    This solver does NOT:
        - guarantee that the solution actually solves the conflict
        - guarantee that the solution is actually feasible
            (not check on feasible speed, climbing rate,
            or other physical and regulatory constraints)
        - check if the given solution would generate more conflicts in a near future
    """

    def __init__(self, stack: Stack) -> None:
        super().__init__(stack=stack)
        LOGGER_MAIN.warning(
            "\n"
            + "-" * 20
            + "\nDISCLAIMER: \nThis is a dummy conflict resolution solver."
            + "\nIt does not provide correct solutions."
            + "\nYou must implement your own solver."
            + "\n"
            + "-" * 20
            + "\n",
        )

    def resolve(
        self,
        conflict: Conflict,
        traf: Traffic,
        current_time: int,
    ) -> list[Solution]:
        """Generates a list of solutions to solve the given conflict.

        Args:
            conflict (Conflict): conflict description.
            traf (list): Traffic information.
            current_time (int): current time.

        Returns:
            list[Solution]: The list of possible solutions to solve the conflict.
        """
        assert isinstance(conflict, Conflict), (
            "Conflict must be an instance of Conflict"
        )

        solutions = []
        execution_time = int(current_time + 30)  # + X seconds

        for callsign in conflict.callsigns:
            idx = traf.id2idx(callsign)
            # Solution 1: change of heading
            s = Solution(
                callsign=callsign,
                commands=[
                    HeadingCommand(time=execution_time, value=traf.hdg[idx] + 45),
                    HeadingCommand(time=execution_time + 60 * 4, value=traf.hdg[idx]),
                ],
            )
            solutions.append(s)

            # Solution 2: change of altitude
            new_alt = int((traf.alt[idx] + 500) // 100) * 100  # +500m
            s = Solution(
                callsign=callsign,
                commands=[
                    AltitudeCommand(time=execution_time, value=new_alt),
                ],
            )
            solutions.append(s)

        # Solution 3: change of speed
        cs = tuple(conflict.callsigns)
        hdg1 = traf.hdg[traf.id2idx(cs[0])]
        hdg2 = traf.hdg[traf.id2idx(cs[1])]

        if (
            abs((hdg1 % 180) - (hdg2 % 180)) < 30
        ):  # The angle between the two aircraft < 30 deg
            # The angle between the two aircraft is two small,
            # changing the speed might not solve the conflict.
            pass
        else:
            for callsign in conflict.callsigns:
                original_speed = round(traf.tas[idx] * 1.943844, 2)  # [knots]
                new_speed = round(traf.tas[idx] * 1.943844 * 0.8, 2)  # -20% [knots]
                s = Solution(
                    callsign=callsign,
                    commands=[
                        SpeedCommand(time=execution_time, value=new_speed),
                        SpeedCommand(
                            time=execution_time + 60 * 2,
                            value=original_speed,
                        ),
                    ],
                )
                solutions.append(s)

        return solutions
