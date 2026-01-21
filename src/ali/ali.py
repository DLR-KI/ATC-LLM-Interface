# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Example of the  Air-traffic-control Language Interface in Bluesky.

This script showcases the use of the Air-traffic-control Language Interface in a Bluesky
scenario with Conflict Detection (CD)
and Conflict Resolution (CR) under natural language policy.

There are two GUI:
- the Bluesky GUI with the radar screen
- a browser UI to display the CD/CR steps, the policy and the LLM generations.

For a given scenario, there are:
- a bluesky scenario with the description of the airspace state
- a policy: the list of rules to follow for CR

The main loop contains 5 main steps:
1. Conflict Detection
2. Generating a list of solutions
3. Filtering the solutions based on the policy
4. Sorting the filtered solutions based on the policy to identify the best solution
5. Executing the best solution
"""

import contextlib
import json
import random
import signal
import sys
import traceback
from datetime import timedelta
from pathlib import Path

import bluesky as bs
import pygame as pg
from bluesky.stack.stackbase import Stack, stack
from bluesky.ui.pygame import splash

from ali.alignment.filtering import FilteringFailureError, filter_solutions
from ali.alignment.policy import ATCPolicy
from ali.alignment.sorting import get_best_solution
from ali.solver.resolution import Conflict, DummySolver, Solution
from ali.ui import app
from ali.ui.logger import LOGGER_ALI, LOGGER_CD, LOGGER_CR, LOGGER_MAIN

# Input files
SCENARIO_PATH = (
    Path(__file__).absolute().parents[2] / "scenarios" / "01_minimal_ali_example"
)

POLICY_PATH = SCENARIO_PATH / "atco-policy.json"
BS_SCN_PATH = SCENARIO_PATH / "bs_scenario.scn"


global run
run: bool = True


def handler_stop_signals(*args) -> None:  # noqa: ANN002
    """A function to properly close on keyboard interrupt.

    It sets global `run` variable to false on keyboard
    interrupt.

    Args:
        args (Any): catching arguments from signals.
    """
    global run
    run = False


signal.signal(signal.SIGINT, handler_stop_signals)
signal.signal(signal.SIGTERM, handler_stop_signals)


def list_conflicts(confpairs: list, dcpa: list, tcpa: list) -> list[Conflict]:
    """List conflicts from Bluesky api as a list of Conflict objects.

    CPA = Closest Point of Approach

    Args:
        confpairs (list): list of conflict between callsign pairs
        dcpa (list): Horizontal distance to CPA
        tcpa (list): time to CPA

    Returns:
        list[Conflict]: List of Conflict objects
    """
    conflicts_list = []
    for idx, conflict in enumerate(confpairs):
        conflicts_list.append(Conflict(conflict, dcpa[idx], tcpa[idx]))

    return conflicts_list


def clean_conflicts_under_resolution(
    conflicts_under_reso: list[Conflict],
    conflicts_under_reso_solution: dict[Conflict, Solution],
    conf_list: list[Conflict],
) -> None:
    """Remove the solved conflicts from conflicts_under_reso.

    Args:
        conflicts_under_reso (list[Conflict]): conflicts which were under resolution.
        conflicts_under_reso_solution (dict[Conflict, Solution]):
            corresponding solutions.
        conf_list (list[Conflict]): list of all conflicts.
    """
    # Clean conflicts_under_resolution
    for idx, rc in enumerate(conflicts_under_reso.copy()):
        if rc not in conf_list:
            # the conflict have been solved
            conflicts_under_reso.pop(idx)
            conflicts_under_reso_solution.pop(rc)
            continue

        # checking if the first command of the resolution have been applied.
        # if so, the conflict should have been resolved.
        solution = conflicts_under_reso_solution[rc]
        first_command_exec_time = solution.commands[0].time
        if timedelta(seconds=bs.sim.simt) > first_command_exec_time + timedelta(
            seconds=20,
        ):
            # the execution time of the first command is passed (by
            # X sec), the conflict should have been resolved by now
            # removing from conflict_under_resolution to be
            # processed again.
            conflicts_under_reso.pop(idx)
            conflicts_under_reso_solution.pop(rc)
            LOGGER_MAIN.warning(
                f"Conflict `{rc}` has not been resolved by the given command. "
                "It will be processed again.",
            )
            # TODO: clean stack from other commands
            # which were part of the initial resolution.


def try_filtering(solutions: list[Solution], policy: ATCPolicy) -> list[Solution]:
    """Filters the solutions that do not fit the ATC Policy.

        Returns only the list of valid solutions. The solutions are unmodified.

    Args:
        solutions (list[Solution]): all solution candidates.
        policy (ATCPolicy): ATC policy.

    Raises:
        FilteringFailureError: Raised if filtering by LLM fails.

    Returns:
        list[Solution]: Returns the list of valid solutions.
    """
    valid_solutions = solutions  # init: all solutions are valid ones
    try:
        # try to filter solutions
        valid_solutions = filter_solutions(
            solutions=solutions,
            policy=policy,
        )

        if len(valid_solutions) == 0:
            raise FilteringFailureError(
                "There is no valid solution after filtering. "
                "Either the policy is too strict, "
                "or the list of solutions not diverse enough, "
                "or the LLM failed to filter properly."
            )
    except Exception as e:
        LOGGER_MAIN.info(
            "Failed to filter solutions due to Exception: " + str(e),
        )
        LOGGER_MAIN.debug(traceback.format_exc())

        # If filtering fails, filtering is skipped.
        # More advanced strategy should be implemented here,
        # depending on the error.
        valid_solutions = solutions
        LOGGER_ALI.warning(
            "# Failed to filter\nFiltering has been skipped.",
        )
    return valid_solutions


def try_sorting(solutions: list[Solution], policy: ATCPolicy) -> Solution:
    """Returns the best solution based on ATC Policy.

    Args:
        solutions (list[Solution]): List of solutions to sort from
        policy (ATCPolicy): ATC Policy containing "sorting policy"

    Returns:
        Solution: The one best solution.
    """
    best_solution = random.choice(
        solutions,
    )  # init: random best solution
    try:
        # try to sort solutions, and give back the best
        best_solution = get_best_solution(
            solutions=solutions,
            policy=policy,
        )
    except Exception as e:
        LOGGER_MAIN.info(
            "Failed to sort solutions due to Exception: " + str(e),
        )
        LOGGER_MAIN.debug(traceback.format_exc())
    return best_solution


def main(
    bs_scn_path: Path = BS_SCN_PATH, policy_path: Path = POLICY_PATH, gui: bool = True
) -> None:
    """BlueSky: Start the mainloop (and possible other threads).

    Args:
        bs_scn_path (Path, optional): bluesky scenario file. Defaults to BS_SCN_PATH.
        policy_path (Path, optional): policy file. Defaults to POLICY_PATH.
        gui (bool, optional): _description_. Defaults to True.

    Raises:
        FileNotFoundError: raised if scenario or policy files are not found.
    """
    if not bs_scn_path.exists():
        raise FileNotFoundError(f"File not found: {bs_scn_path}")
    if not policy_path.exists():
        raise FileNotFoundError(f"File not found: {policy_path}")

    # Loading files
    policy = ATCPolicy(policy_path)

    if gui:
        splash.show()
        bs.init(mode="sim", gui="pygame", scenfile=str(bs_scn_path))
        bs.sim.op()
        bs.scr.init()
        bs.scr.update()

        with contextlib.suppress(TypeError):
            # removing empty file loading which pops a blocking file loader at the
            # beginning
            Stack.cmdstack.remove(("IC", None))
    else:
        bs.init(mode="sim", detached=True, scenfile=str(bs_scn_path))

    bs.sim.op()

    # bs.sim.set_dtmult(mult=0.01)  # run simulation X time faster

    # Gradio: setup app
    app.init(policy=policy, gui=gui)
    # Main loop with: simulation, UI, and CD/CR
    conflicts_under_resolution: list[Conflict] = []
    conflicts_under_resolution_solution: dict[Conflict, Solution] = {}

    conflict_solver = DummySolver(stack=stack)

    while (bs.sim.state != bs.END) and run:
        bs.sim.update()  # Update sim
        if gui:
            bs.scr.update()  # GUI update

        conf_list = list_conflicts(
            bs.traf.cd.confpairs_unique,
            bs.traf.cd.dcpa,
            bs.traf.cd.tcpa,
        )

        clean_conflicts_under_resolution(
            conflicts_under_resolution, conflicts_under_resolution_solution, conf_list
        )

        if len(conf_list) > 0:
            # there are unresolved conflicts
            for idx, conflict in enumerate(conf_list):
                if conflict in conflicts_under_resolution:
                    # ignoring conflict under resolution
                    # (waiting for the commands to be executed by pilot)
                    continue

                LOGGER_CD.info(
                    "# Details of conflict:\n"
                    "\n```"
                    f"\nCallsigns: \t\t{conflict}"
                    f"\nDist to conflict : \t{bs.traf.cd.dcpa[idx]:.2f}"
                    f"\nTime to conflict (s): \t{bs.traf.cd.tcpa[idx]:.2f}"
                    "\n```",
                )

                # CR solver provides a list of solutions
                solutions = conflict_solver.resolve(conflict, bs.traf, bs.sim.simt)
                LOGGER_CR.debug(
                    "\n# Solutions:"
                    "\n```json"
                    "\n"
                    + json.dumps(
                        [s.to_json() for s in solutions],
                        indent=4,
                        default=str,
                    )
                    + "\n```",
                )
                """Filtering."""
                valid_solutions = try_filtering(solutions=solutions, policy=policy)
                """Sorting."""
                best_solution = try_sorting(solutions=valid_solutions, policy=policy)

                LOGGER_ALI.info(
                    f"# Best solution to be executed by datco: \
                    \n ```json\n{best_solution.pretty_print()}\n```",
                )
                # Execution of the best solution
                conflict_solver.apply_solution(best_solution)
                conflicts_under_resolution.append(conflict)
                conflicts_under_resolution_solution[conflict] = best_solution

    bs.sim.quit()
    pg.quit()

    LOGGER_MAIN.info("BlueSky normal end.")


if __name__ == "__main__":
    gui = "--no-gui" not in sys.argv
    main(gui=gui)
