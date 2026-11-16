import pytest

from experiments.rubricbench_calibration.run import _config_from_args, build_parser


def test_default_output_dir_is_outputs():
    args = build_parser().parse_args(["analyze"])
    config = _config_from_args(args)
    assert config.output_dir.name == "outputs"
    assert config.disagreement_policy == "exclude"


def test_sampling_shared_routes_to_outputs_shared():
    args = build_parser().parse_args(["analyze", "--sampling", "shared"])
    config = _config_from_args(args)
    assert config.output_dir.name == "shared"
    assert config.output_dir.parent.name == "outputs"


def test_policy_annotator_1_routes_to_outputs_policy_annotator_1():
    args = build_parser().parse_args(["analyze", "--policy", "annotator_1"])
    config = _config_from_args(args)
    assert config.disagreement_policy == "annotator_1"
    assert config.output_dir.name == "policy_annotator_1"
    assert config.output_dir.parent.name == "outputs"


def test_policy_annotator_2_and_sampling_unstratified_nest_output_dir():
    args = build_parser().parse_args(["analyze", "--policy", "annotator_2", "--sampling", "unstratified"])
    config = _config_from_args(args)
    assert config.disagreement_policy == "annotator_2"
    assert config.output_dir.name == "unstratified"
    assert config.output_dir.parent.name == "policy_annotator_2"
    assert config.output_dir.parent.parent.name == "outputs"


def test_policy_rejects_unknown_value():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["analyze", "--policy", "bogus"])


def test_policy_available_on_all_subcommand_too():
    args = build_parser().parse_args(["all", "--policy", "annotator_1"])
    config = _config_from_args(args)
    assert config.disagreement_policy == "annotator_1"
    assert config.output_dir.name == "policy_annotator_1"
