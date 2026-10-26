import io
from pathlib import Path

import pytest

from shipcost.cli import main


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    path = tmp_path / "data"
    monkeypatch.setenv("SHIPCOST_DATA_DIR", str(path))
    return path


@pytest.fixture
def demo(data_dir):
    assert main(["demo"]) == 0
    return data_dir / "rates.csv"


@pytest.fixture
def sample_csv_path():
    from importlib.resources import as_file, files

    with as_file(files("shipcost") / "examples" / "sample_rate_table.csv") as p:
        yield Path(p)


@pytest.fixture
def run_cli(monkeypatch):
    def run(*argv, stdin=None):
        if stdin is not None:
            monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        monkeypatch.setattr("sys.stderr", io.StringIO())
        import sys

        code = main(list(argv))
        return code, sys.stdout.getvalue(), sys.stderr.getvalue()

    return run
