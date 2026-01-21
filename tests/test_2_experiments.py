# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Testing ALI experiments."""

from pathlib import Path

from ali.experiments.filtering import dataset as filter_dataset
from ali.experiments.filtering import run as filter_run
from ali.experiments.sorting import dataset as sort_dataset
from ali.experiments.sorting import run as sort_run


def test_filtering_dataset_creation(tmp_path: Path):
    """Test the make, load and analyse dataset functions.

    Args:
        tmp_path (Path): temporary path to create a dataset.
    """

    dataset_path = tmp_path / "dataset-test-filter.jsonl"

    filter_dataset.make(file_path=dataset_path, n_solutions=5, max_n_commands=5)

    header, dataset = filter_dataset.load(file_path=dataset_path)

    assert len(header) > 0
    for k in ["id", "solution", "policy", "violation", "explanation"]:
        assert k in header
    assert len(dataset) > 0

    assert len(dataset[0][0]) > 0

    assert len(dataset[0][1].get("callsign")) > 0
    assert len(dataset[0][1].get("commands")) > 0
    assert len(dataset[0][1].get("commands")[0].get("command")) > 0

    assert len(dataset[0][2]) > 0

    assert isinstance(dataset[0][3], bool)

    assert len(dataset[0][4]) > 0

    filter_dataset.analyse_dataset(header, dataset, plot=False)


def test_sorting_dataset_creation(tmp_path: Path):
    """Test the make, load and analyse dataset functions.

    Args:
        tmp_path (Path): temporary path to create a dataset.
    """

    dataset_path = tmp_path / "dataset-test-sort.jsonl"

    sort_dataset.make(file_path=dataset_path, n_solutions=5, max_n_commands=5)

    header, dataset = sort_dataset.load(file_path=dataset_path)

    assert len(header) > 0
    for k in [
        "id",
        "solution_1",
        "solution_2",
        "policy",
        "acceptable_solutions",
        "explanation",
    ]:
        assert k in header
    assert len(dataset) > 0

    assert len(dataset[0][0]) > 0

    for solution_idx in [1, 2]:
        assert len(dataset[0][solution_idx].get("callsign")) > 0
        assert len(dataset[0][solution_idx].get("commands")) > 0
        assert len(dataset[0][solution_idx].get("commands")[0].get("command")) > 0

    assert len(dataset[0][3]) > 0

    assert isinstance(dataset[0][4], int)

    assert len(dataset[0][5]) > 0

    sort_dataset.analyse_dataset(header, dataset, plot=False)


def test_filtering_run_experiment(tmp_path: Path):
    """Running the experiments and checking the existence of the results files.

    Args:
        tmp_path (Path): Temporary dir to store dataset and results.
    """
    dataset_path = tmp_path / "dataset-test-filter-run.jsonl"
    results_dir = tmp_path / "results-filter"
    dataset_name = dataset_path.stem.replace("dataset-", "")

    filter_dataset.make(file_path=dataset_path, n_solutions=5, max_n_commands=5)

    filter_run.main(dataset_path=dataset_path, results_dir=results_dir)

    results_tables = list(results_dir.glob(f"*__{dataset_name}__results*.csv"))

    assert len(results_tables) > 0

    for path in results_tables:
        text = path.read_text()
        assert len(text) > 0


def test_sorting_run_experiment(tmp_path: Path):
    """Running the experiments and checking the existence of the results files.

    Args:
        tmp_path (Path): Temporary dir to store dataset and results.
    """
    dataset_path = tmp_path / "dataset-test-sort-run.jsonl"
    results_dir = tmp_path / "results-sort"
    dataset_name = dataset_path.stem.replace("dataset-", "")

    sort_dataset.make(file_path=dataset_path, n_solutions=5, max_n_commands=5)

    sort_run.main(dataset_path=dataset_path, results_dir=results_dir)

    results_tables = list(results_dir.glob(f"*__{dataset_name}__results*.csv"))

    assert len(results_tables) > 0

    for path in results_tables:
        text = path.read_text()
        assert len(text) > 0
