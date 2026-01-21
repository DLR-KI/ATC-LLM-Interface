# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Run the experiment."""

import datetime
import logging
from itertools import starmap
from pathlib import Path

import pandas as pd

from ali.alignment import filtering, llm, policy
from ali.experiments.filtering.dataset import load
from ali.ui.logger import LOGGER_ALI

DATASET_PATH = Path(__file__).parent / "dataset.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"


def main(
    dataset_path: Path = DATASET_PATH,
    results_dir: Path = RESULTS_DIR,
    llm_options: llm.OllamaOptions = llm.ollama_options,
) -> None:
    """Run the experiment and store the results.

    Args:
        dataset_path (Path, optional): Defaults to DATASET_PATH.
        results_dir (Path, optional): dir to store results. Defaults to RESULTS_DIR.
        llm_options (llm.OllamaOptions, optional): Ollama generation option.
            Defaults to llm.default_options.
    """
    dataset_name = dataset_path.stem.replace("dataset-", "")
    print(dataset_path.stem)
    """Storing the results."""
    results_dir.mkdir(exist_ok=True)

    handlers = []

    # adding file handler to ali log (to catch the LLM answers)
    formatter = logging.Formatter("%(message)s")
    date = datetime.datetime.now().isoformat().split(".")[0].replace(":", "-")
    log_file_path = results_dir / f"{date}__{dataset_name}__ali.log"
    fh = logging.FileHandler(str(log_file_path), "w")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    LOGGER_ALI.addHandler(fh)
    handlers.append(fh)

    # Results logger
    logger = logging.getLogger("results")
    logger.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)10s - %(levelname)8s - %(message)s",
    )

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # create file handler
    log_file_path = results_dir / f"{date}__{dataset_name}__results-debug.log"
    fh = logging.FileHandler(str(log_file_path), "w")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # create file handler
    log_file_path = results_dir / f"{date}__{dataset_name}__results-info.log"
    fh = logging.FileHandler(str(log_file_path), "w")
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    """Loading inputs."""
    logger.info(f'Loading data from: "{dataset_path}"')
    _header, dataset = load(dataset_path)
    logger.info(f"Dataset size: {len(dataset)}")

    logger.info(f"LLM config: {llm.CONFIG_DICT}")
    llm.ollama_options = llm_options
    logger.info(f"LLM options: {llm.ollama_options}")
    """Running experiment."""
    logger.info("Starting experiment")
    results = pd.DataFrame()

    success_tot = 0

    for idx, data in enumerate(dataset):
        if idx % 50 == 0:
            print(f"Progress: {idx}/{len(dataset)}")
        print(".")
        datapoint_id, solution_raw, rules_raw, violation, _explanation = data

        LOGGER_ALI.debug(
            "#" * 10 + f" data entry no: {idx} - id: {datapoint_id} " + "#" * 10,
        )
        logger.debug(f"Data entry no: {idx} - id: {datapoint_id} ")

        rules = policy.ATCPolicy()
        rules.filtering_rules = list(starmap(policy.Rule, rules_raw.items()))

        for _attempt in range(10):
            try:
                filtered_list = filtering.filter_solutions(
                    solutions=[solution_raw],
                    policy=rules,
                )

                success = violation == (len(filtered_list) == 0)
                if not success:
                    LOGGER_ALI.debug(
                        "#" * 10 + " Filtering (above) was not a success " + "#" * 10,
                    )
                break
            except Exception as e:
                logger.debug(f"Failed to filter due to error: {e}")
                pass
        else:
            logger.error("failed to filter after 10 times")
            success = False

        success_tot += success

        result = pd.DataFrame({"id": datapoint_id, "success": [success]})

        results = pd.concat([results, result])

    success_tot = results["success"].sum()
    success_rate = success_tot * 100 // len(dataset)
    logger.info(f"Success: {success_tot} / {len(dataset)} ({success_rate}%)")
    results.to_csv(
        results_dir / f"{date}__{dataset_name}__results-table.csv",
        sep=";",
        header=True,
    )

    for h in handlers:
        LOGGER_ALI.removeHandler(h)
        logger.removeHandler(h)


if __name__ == "__main__":
    SEED = 1

    # for dataset in Path(__file__).parent.glob('dataset*.jsonl'):
    llm_options = llm.OllamaOptions(temperature=-1)
    main(dataset_path=DATASET_PATH, llm_options=llm_options)
    for temperature, top_p in zip([0.5, 0.9], [0.5, 0.95], strict=False):
        llm_options = llm.OllamaOptions(seed=SEED, temperature=temperature, top_p=top_p)
        main(dataset_path=DATASET_PATH, llm_options=llm_options)
