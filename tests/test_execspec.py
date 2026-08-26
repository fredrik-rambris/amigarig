import pytest

from amigarig.assigns import AssignTable
from amigarig.execspec import (
    DEFAULT_FAILAT,
    DEFAULT_STAGE,
    ExecError,
    normalize_exec_item,
    run_exec_item,
    run_exec_stage,
)
from amigarig.log import set_verbosity


def _tmp_dir_factory(tmp_path):
    counter = {"n": 0}

    def make():
        counter["n"] += 1
        path = tmp_path / f"t{counter['n']}"
        path.mkdir()
        return path

    return make


def test_normalize_defaults():
    item = normalize_exec_item({"cmd": "echo hi"})
    assert item == {
        "stage": DEFAULT_STAGE,
        "cmd": "echo hi",
        "cwd": None,
        "input": None,
        "output": None,
        "env": {},
        "failat": DEFAULT_FAILAT,
    }


def test_normalize_rejects_unknown_stage():
    with pytest.raises(ValueError):
        normalize_exec_item({"stage": "during", "cmd": "echo hi"})


def test_normalize_rejects_missing_cmd():
    with pytest.raises(TypeError):
        normalize_exec_item({"stage": "init"})


def test_normalize_rejects_empty_cmd_list():
    with pytest.raises(TypeError):
        normalize_exec_item({"cmd": []})


def test_normalize_rejects_non_string_list_items():
    with pytest.raises(TypeError):
        normalize_exec_item({"cmd": ["echo", 1]})


def test_normalize_accepts_list_cmd():
    item = normalize_exec_item({"cmd": ["echo", "hi"], "priority": 1})
    assert item["cmd"] == ["echo", "hi"]


def test_run_exec_item_string_cmd_runs_through_shell(tmp_path):
    assigns = AssignTable()
    out_file = tmp_path / "out.txt"
    item = normalize_exec_item({"cmd": f"echo hello > {out_file}"})

    run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))

    assert out_file.read_text().strip() == "hello"


def test_run_exec_item_list_cmd_runs_argv_directly(tmp_path):
    assigns = AssignTable()
    out_file = tmp_path / "out.txt"
    item = normalize_exec_item({"cmd": ["sh", "-c", f"echo hi > {out_file}"]})

    run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))

    assert out_file.read_text().strip() == "hi"


def test_run_exec_item_sets_tmpdir_and_defaults_cwd_to_it(tmp_path):
    assigns = AssignTable()
    item = normalize_exec_item({"cmd": "pwd > $TMPDIR/where; env | grep ^TMPDIR= > $TMPDIR/tmpdir_env"})

    run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))

    invocation_dir = tmp_path / "t1"
    assert invocation_dir.joinpath("where").read_text().strip() == str(invocation_dir)
    assert invocation_dir.joinpath("tmpdir_env").read_text().strip() == f"TMPDIR={invocation_dir}"


def test_run_exec_item_cwd_resolved_through_assigns(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    assigns = AssignTable({"proj": str(real_dir)})
    out_file = real_dir / "out.txt"
    item = normalize_exec_item({"cmd": "pwd > out.txt", "cwd": "proj:"})

    run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))

    assert out_file.read_text().strip() == str(real_dir)


def test_run_exec_item_env_is_jinja_rendered(tmp_path):
    assigns = AssignTable({"wb": str(tmp_path)})
    out_file = tmp_path / "out.txt"
    item = normalize_exec_item(
        {
            "cmd": f"echo $CPU $WB > {out_file}",
            "env": {"CPU": "{{ config.fsuae.cpu }}", "WB": "{{ assign('wb:') }}"},
        }
    )

    run_exec_item(
        item,
        assigns=assigns,
        config={"fsuae": {"cpu": "68030"}},
        make_tmp_dir=_tmp_dir_factory(tmp_path),
    )

    assert out_file.read_text().strip() == f"68030 {tmp_path}"


def test_run_exec_item_output_captures_stdout(tmp_path):
    assigns = AssignTable()
    out_file = tmp_path / "captured.txt"
    item = normalize_exec_item({"cmd": ["echo", "hello"], "output": str(out_file)})

    run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))

    assert out_file.read_text().strip() == "hello"


def test_run_exec_item_input_feeds_stdin(tmp_path):
    assigns = AssignTable()
    in_file = tmp_path / "seed.txt"
    in_file.write_text("from-file\n")
    out_file = tmp_path / "out.txt"
    item = normalize_exec_item(
        {"cmd": ["cat"], "input": str(in_file), "output": str(out_file)}
    )

    run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))

    assert out_file.read_text() == "from-file\n"


def test_run_exec_item_input_output_resolved_through_assigns(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "seed.txt").write_text("seeded\n")
    assigns = AssignTable({"proj": str(real_dir)})
    item = normalize_exec_item({"cmd": ["cat"], "input": "proj:seed.txt", "output": "proj:out.txt"})

    run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))

    assert (real_dir / "out.txt").read_text() == "seeded\n"


def test_run_exec_item_default_failat_raises_on_nonzero(tmp_path):
    assigns = AssignTable()
    item = normalize_exec_item({"cmd": "exit 1"})

    with pytest.raises(ExecError):
        run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))


def test_run_exec_item_higher_failat_tolerates_lower_codes(tmp_path):
    assigns = AssignTable()
    item = normalize_exec_item({"cmd": "exit 3", "failat": 4})

    run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))


def test_run_exec_item_failat_still_raises_at_threshold(tmp_path):
    assigns = AssignTable()
    item = normalize_exec_item({"cmd": "exit 4", "failat": 4})

    with pytest.raises(ExecError):
        run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))


def test_run_exec_stage_runs_only_matching_stage_in_order(tmp_path):
    assigns = AssignTable()
    out_file = tmp_path / "order.txt"
    items = [
        {"stage": "before", "cmd": f"echo before1 >> {out_file}"},
        {"stage": "init", "cmd": f"echo init >> {out_file}"},
        {"stage": "before", "cmd": f"echo before2 >> {out_file}"},
        {"stage": "after", "cmd": f"echo after >> {out_file}"},
    ]

    run_exec_stage(
        items, "before", assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path)
    )

    assert out_file.read_text().splitlines() == ["before1", "before2"]


def test_run_exec_item_verbose_prints_argv_and_cwd(tmp_path, log_messages):
    assigns = AssignTable()
    item = normalize_exec_item({"cmd": ["true"]})

    set_verbosity(1)
    run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))

    out = "\n".join(log_messages)
    assert "['true']" in out
    assert "cwd=" in out


def test_run_exec_item_not_verbose_prints_nothing(tmp_path, log_messages):
    assigns = AssignTable()
    item = normalize_exec_item({"cmd": ["true"]})

    set_verbosity(0)
    run_exec_item(item, assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path))

    assert log_messages == []


def test_run_exec_stage_validates_whole_list_up_front(tmp_path):
    assigns = AssignTable()
    items = [
        {"stage": "init", "cmd": "true"},
        {"stage": "after", "cmd": []},  # invalid, but not the stage being run
    ]

    with pytest.raises(TypeError):
        run_exec_stage(
            items, "init", assigns=assigns, config={}, make_tmp_dir=_tmp_dir_factory(tmp_path)
        )
