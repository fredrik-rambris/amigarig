from amigarig.config.merge import merge, merge_chain


def test_dict_deep_merge_preserves_untouched_keys():
    base = {"copy": {"c": ["A", "B"], "libs": ["x"]}}
    override = {"copy": {"fonts": ["y"]}}
    result = merge(base, override)
    assert result == {"copy": {"c": ["A", "B"], "libs": ["x"], "fonts": ["y"]}}


def test_list_replaces_by_default():
    base = {"copy": {"c": ["A", "B"]}}
    override = {"copy": {"c": ["Z"]}}
    result = merge(base, override)
    assert result == {"copy": {"c": ["Z"]}}


def test_plus_key_appends_instead_of_replacing():
    base = {"copy": {"fonts": ["topaz/8"]}}
    override = {"copy": {"+fonts": ["Garamond/9"]}}
    result = merge(base, override)
    assert result == {"copy": {"fonts": ["topaz/8", "Garamond/9"]}}


def test_plus_key_on_missing_base_just_sets_list():
    result = merge({}, {"copy": {"+fonts": ["a"]}})
    assert result == {"copy": {"fonts": ["a"]}}


def test_scalar_replace():
    result = merge({"cpu": "68000"}, {"cpu": "68030"})
    assert result == {"cpu": "68030"}


def test_merge_chain_left_to_right():
    layers = [{"a": 1}, {"a": 2, "b": 3}, {"b": 4}]
    assert merge_chain(layers) == {"a": 2, "b": 4}


def test_top_level_plus_key():
    layers = [{"startup": ["cd Project:"]}, {"+startup": ["NoBorder"]}]
    assert merge_chain(layers) == {"startup": ["cd Project:", "NoBorder"]}
