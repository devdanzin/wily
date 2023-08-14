import pathlib
import sys
from unittest import mock

path = str(pathlib.Path(__file__).parents[2] / "src")
sys.path.insert(0, path)

import annotator


def test_get_metric_color():
    pure_green = "rgba(0, 255, 0, 0.75)"
    assert annotator.get_metric_color(0) == pure_green
    assert annotator.get_metric_color(0, maximum=1000) == pure_green
    assert annotator.get_metric_color(0, maximum=1) == pure_green
    pure_red = "rgba(255, 0, 0, 0.75)"
    assert annotator.get_metric_color(51) == pure_red
    assert annotator.get_metric_color(1001, maximum=1000) == pure_red
    assert annotator.get_metric_color(2, maximum=1) == pure_red
    yellow = "rgba(255, 255, 0, 0.75)"
    assert annotator.get_metric_color(26) == yellow
    assert annotator.get_metric_color(501, maximum=1000) == yellow
    assert annotator.get_metric_color(1.5, maximum=1) == yellow
    for name, maximum in annotator.MAX_DICT.items():
        assert annotator.get_metric_color(0, name=name) == pure_green
        assert annotator.get_metric_color(maximum + 1, name=name) == pure_red
        assert annotator.get_metric_color(maximum / 2 + 1, name=name) == yellow
    # Test that maximum is ignored when a name is passed
    assert annotator.get_metric_color(maximum / 2 + 1, maximum=1, name=name) == yellow


def test_last_line():
    details = {str(i): {"endline": i} for i in range(100)}
    assert annotator.last_line(details) == 99
    details = {str(i): {"endline": 10} for i in range(100)}
    assert annotator.last_line(details) == 10
    details = {str(i): {} for i in range(100)}
    assert annotator.last_line(details) == 0
    details = {}
    assert annotator.last_line(details) == 0



