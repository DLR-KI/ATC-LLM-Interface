# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""A very basic description of CR commands.

A Command has:
- a type: [Heading, Altitude, Speed]
- a time: when to execute the command
- a value: the desired Heading/Altitude/Speed
"""

from abc import abstractmethod
from datetime import timedelta


class CommandBase:
    """Abstract class for commands.

    Commands are clearance to send to aircraft.
    A command contains:
    - an execution time
    - a type: [heading, altitude, speed]
    - a value to be changed
    - a command in natural language.
    """

    time: timedelta
    value: int

    def __init__(self, time: int, value: float) -> None:
        """Creation of a command.

        Args:
            time (int): execution time in seconds,
            value (int | float): new value for the parameter to be changed.
                This is specific to the command type (Heading/Altitude/Speed)
        """
        if isinstance(time, int):
            # assuming time was given as seconds
            time_delta = timedelta(seconds=time)
        assert isinstance(time_delta, timedelta)
        assert isinstance(value, (float, int))

        value = int(value)

        self.time = time_delta
        self.value = value

    def __repr__(self) -> str:
        return str({
            "time": str(self.time),
            "value": self.value,
            "command": self.natural_command(),
        })

    def __str__(self) -> str:
        return self.__repr__()

    def to_json(self) -> dict:
        """To JSON serializable format.

        Returns:
            dict: JSON serializable object (and nested objects.)
        """
        return {
            "time": str(self.time),
            "value": self.value,
            "command": self.natural_command(),
        }

    @abstractmethod
    def bluesky_command(self, callsign: str) -> str:
        """Generates a Bluesky-interpretable command.

        Args:
            callsign (str): callsign of the aircraft to send the command to.

        Returns:
            str: Bluesky-interpretable command.
        """
        return "BlueSky command"

    @abstractmethod
    def natural_command(self) -> str:
        """Generates a command in natural language.

        Returns:
            str: command in natural language.
        """
        return "Command"


class HeadingCommand(CommandBase):
    """A command requesting a change of heading."""

    def natural_command(self) -> str:
        """Generates a command in natural language.

        Returns:
            str: command in natural language.
        """
        return f"Change heading to {self.value}deg"

    def bluesky_command(self, callsign: str) -> str:
        """Generates a Bluesky-interpretable command.

        Args:
            callsign (str): callsign of the aircraft to send the command to.

        Returns:
            str: Bluesky-interpretable command.
        """
        return f"HDG {callsign}, {self.value}"


class AltitudeCommand(CommandBase):
    """A command requesting a change of Altitude."""

    def natural_command(self) -> str:
        """Generates a command in natural language.

        Returns:
            str: command in natural language.
        """
        return f"Change altitude to {self.value}m"

    def bluesky_command(self, callsign: str) -> str:
        """Generates a Bluesky-interpretable command.

        Args:
            callsign (str): callsign of the aircraft to send the command to.

        Returns:
            str: Bluesky-interpretable command.
        """
        return f"ALT {callsign}, {self.value}"


class SpeedCommand(CommandBase):
    """A command requesting a change of Altitude."""

    def natural_command(self) -> str:
        """Generates a command in natural language.

        Returns:
            str: command in natural language.
        """
        return f"Change speed to {self.value}m/s"

    def bluesky_command(self, callsign: str) -> str:
        """Generates a Bluesky-interpretable command.

        Args:
            callsign (str): callsign of the aircraft to send the command to.

        Returns:
            str: Bluesky-interpretable command.
        """
        return f"SPD {callsign}, {self.value}"
