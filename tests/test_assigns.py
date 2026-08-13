from pathlib import Path

import pytest

from amigarig.assigns import AssignTable, AssignError


def test_absolute_path_bypasses_assigns():
    table = AssignTable({})
    assert table.resolve("/some/absolute/path") == Path("/some/absolute/path")


def test_single_assign():
    table = AssignTable({"fsuae": "/home/boost/Data/FS-UAE"})
    assert table.resolve("fsuae:workbench3.1") == Path("/home/boost/Data/FS-UAE/workbench3.1")


def test_chained_assign():
    table = AssignTable(
        {
            "fsuae": "/home/boost/Data/FS-UAE",
            "wb": "fsuae:workbench1.3",
        }
    )
    assert table.resolve("wb:C/Copy") == Path("/home/boost/Data/FS-UAE/workbench1.3/C/Copy")


def test_unknown_assign_raises():
    table = AssignTable({})
    with pytest.raises(AssignError, match="unknown assign"):
        table.resolve("wb:C")


def test_cycle_detection():
    table = AssignTable({"a": "b:x", "b": "a:y"})
    with pytest.raises(AssignError, match="cycle"):
        table.resolve("a:z")
