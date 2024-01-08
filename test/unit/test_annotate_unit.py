from unittest import mock

import wily.commands.annotate


def test_get_metric_color():
    pure_green = "rgba(0, 255, 0, 0.75)"
    assert wily.commands.annotate.get_metric_color(0) == pure_green
    assert wily.commands.annotate.get_metric_color(0, maximum=1000) == pure_green
    assert wily.commands.annotate.get_metric_color(0, maximum=1) == pure_green
    pure_red = "rgba(255, 0, 0, 0.75)"
    assert wily.commands.annotate.get_metric_color(51) == pure_red
    assert wily.commands.annotate.get_metric_color(1001, maximum=1000) == pure_red
    assert wily.commands.annotate.get_metric_color(2, maximum=1) == pure_red
    yellow = "rgba(255, 255, 0, 0.75)"
    assert wily.commands.annotate.get_metric_color(26) == yellow
    assert wily.commands.annotate.get_metric_color(501, maximum=1000) == yellow
    assert wily.commands.annotate.get_metric_color(1.5, maximum=1) == yellow
    for name, maximum in wily.commands.annotate.MAX_DICT.items():
        assert wily.commands.annotate.get_metric_color(0, name=name) == pure_green
        assert (
            wily.commands.annotate.get_metric_color(maximum + 1, name=name) == pure_red
        )
        assert (
            wily.commands.annotate.get_metric_color(maximum / 2 + 1, name=name)
            == yellow
        )
    # Test that maximum is ignored when a name is passed
    assert (
        wily.commands.annotate.get_metric_color(maximum / 2 + 1, maximum=1, name=name)
        == yellow
    )


def test_last_line():
    details = {str(i): {"endline": i} for i in range(100)}
    assert wily.commands.annotate.last_line(details) == 99
    details = {str(i): {"endline": 10} for i in range(100)}
    assert wily.commands.annotate.last_line(details) == 10
    details = {str(i): {} for i in range(100)}
    assert wily.commands.annotate.last_line(details) == 0
    details = {}
    assert wily.commands.annotate.last_line(details) == 0


def test_append_css():
    css_out = mock.MagicMock()
    css_out.open = mock.MagicMock(return_value=css_out)
    css_out.__enter__ = mock.MagicMock(return_value=css_out)
    styles = {"one": "color1", "two": "color2", "three": "color1"}
    wily.commands.annotate.append_css(css_out, styles)
    print(css_out.mock_calls)
    css_out.write.assert_called_once_with(
        "\n\n"
        ".one, .three { background-color: color1;}\n"
        ".two { background-color: color2;}"
    )
