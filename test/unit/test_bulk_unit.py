import pathlib
from unittest import mock

import wily.commands.bulk


def test_get_all_tracked():
    returned_files = "Mocked.py\n\nnot_included\n   \nincluded.py"
    mock_execute = mock.Mock(return_value=returned_files)
    kwargs = {"git.execute": mock_execute}
    mock_repo = mock.Mock(**kwargs)
    mock_Repo = mock.Mock(return_value=mock_repo)
    with mock.patch("bulk_wily.Repo", mock_Repo):
        result = wily.commands.bulk.get_all_tracked(mock.Mock())
    assert result == [pathlib.Path("Mocked.py"), pathlib.Path("included.py")]


def test_list_metrics_real_metrics():
    metrics = [
        "complexity",
        "h1",
        "h2",
        "N1",
        "N2",
        "vocabulary",
        "length",
        "volume",
        "difficulty",
        "effort",
        "mi",
        "loc",
        "lloc",
        "sloc",
        "comments",
        "multi",
        "blank",
        "single_comments",
    ]
    result = wily.commands.bulk.list_all_metrics()
    assert result == metrics


def test_list_metrics_mock_metrics():
    bare_operator_metrics = {"operator_cls.metrics": []}
    mock_bare_operator = mock.Mock(**bare_operator_metrics)  # type: ignore
    single_metric = mock.Mock()
    single_metric.name = "single_metric"
    single_operator_metrics = {"operator_cls.metrics": [single_metric]}
    mock_single_operator = mock.Mock(**single_operator_metrics)  # type: ignore
    multiple_metric1 = mock.Mock()
    multiple_metric1.name = "multiple_metric1"
    multiple_metric2 = mock.Mock()
    multiple_metric2.name = "multiple_metric2"
    multiple_operator_metrics = {"operator_cls.metrics": [multiple_metric1, multiple_metric2]}
    mock_multiple_operator = mock.Mock(**multiple_operator_metrics)  # type: ignore
    operators = {
        "bare_operator": mock_bare_operator,
        "single_operator": mock_single_operator,
        "multiple_operator": mock_multiple_operator,
    }
    with mock.patch("bulk_wily.ALL_OPERATORS", operators):
        result = wily.commands.bulk.list_all_metrics()
        assert result == [
            "bare_operator",
            "multiple_metric1",
            "multiple_metric2",
            "single_metric",
        ]


def test_get_headers_no_metrics():
    nl_indent = "\n            "
    default_headers = nl_indent.join(
        ["<th><h3>Filename</h3></th>", "<th><h3>Report</h3></th>"]
    )
    no_metrics_result = wily.commands.bulk.get_headers([])
    assert no_metrics_result == default_headers


def test_get_headers_metrics():
    nl_indent = "\n            "
    default_headers = nl_indent.join(
        ["<th><h3>Filename</h3></th>", "<th><h3>Report</h3></th>"]
    )
    metrics = ["metric1", "metric3", "metric3"]
    metric_headers = """
            <th><h3>metric1</h3></th>
            <th><h3>metric3</h3></th>
            <th><h3>metric3</h3></th>"""
    metrics_result = wily.commands.bulk.get_headers(metrics)
    assert metrics_result == default_headers + metric_headers


def test_link_if_exists_link():
    mock_path = mock.MagicMock()
    columns = []
    wily.commands.bulk.link_if_exists(columns, "filename.html", "metric", mock_path)
    assert columns[0] == '<td><a href="filename.html">metric</a></td>'


def test_link_if_exists_no_link():
    mock_path = mock.MagicMock()
    mock_exists = mock.Mock(return_value=False)
    mock_exists.exists = mock_exists
    mock_path.__truediv__.return_value = mock_exists
    columns = []
    wily.commands.bulk.link_if_exists(columns, "filename.html", "metric", mock_path)
    assert columns[0] == "<td>metric</td>"


def test_generate_global_row_empty():
    nl_indent = "\n            "

    mock_path = mock.MagicMock()
    mock_exists = mock.Mock(return_value=False)
    mock_exists.exists = mock_exists
    mock_path.__truediv__.return_value = mock_exists

    empty_header = """
        <tr>
            <th>global</th>
            <td></td>
        </tr>"""
    metrics = []
    result = wily.commands.bulk.generate_global_row(metrics, nl_indent, mock_path)
    assert result == empty_header


def test_generate_global_row_with_metrics():
    nl_indent = "\n            "

    mock_path = mock.MagicMock()
    mock_exists = mock.Mock(return_value=False)
    mock_exists.exists = mock_exists
    mock_path.__truediv__.return_value = mock_exists

    with_metrics = """
        <tr>
            <th>global</th>
            <td></td>
            <td>metric1</td>
            <td>metric2</td>
        </tr>"""
    metrics = ["metric1", "metric2"]
    result = wily.commands.bulk.generate_global_row(metrics, nl_indent, mock_path)
    assert result == with_metrics


def test_generate_global_row_with_linked_metrics():
    nl_indent = "\n            "

    mock_path = mock.MagicMock()
    mock_exists = mock.Mock(return_value=True)
    mock_exists.exists = mock_exists
    mock_path.__truediv__.return_value = mock_exists

    with_linked_metrics = """
        <tr>
            <th>global</th>
            <td></td>
            <td><a href="global_metric1.html">metric1</a></td>
            <td><a href="global_metric2.html">metric2</a></td>
        </tr>"""
    metrics = ["metric1", "metric2"]
    result = wily.commands.bulk.generate_global_row(metrics, nl_indent, mock_path)
    assert result == with_linked_metrics


def test_generate_table_row():
    nl_indent = "\n            "

    mock_path = mock.MagicMock()
    mock_exists = mock.Mock(return_value=False)
    mock_exists.exists = mock_exists
    mock_path.__truediv__.return_value = mock_exists

    filename = "test.py"
    htmlname = "test.py"

    no_metrics_no_files = """
        <tr>
            <th>test.py</th>
            <td>Report</td>
        </tr>"""
    metrics = []
    result = wily.commands.bulk.generate_table_row(
        filename, htmlname, metrics, nl_indent, mock_path
    )
    assert result == no_metrics_no_files

    metrics_no_files = """
        <tr>
            <th>test.py</th>
            <td>Report</td>
            <td>metric1</td>
            <td>metric2</td>
        </tr>"""
    metrics = ["metric1", "metric2"]
    result = wily.commands.bulk.generate_table_row(
        filename, htmlname, metrics, nl_indent, mock_path
    )
    assert result == metrics_no_files

    mock_exists.return_value = True
    no_metrics_with_files = """
        <tr>
            <th><a href="annotated_test.py.html">test.py</a></th>
            <td><a href="test.py_report.html">Report</a></td>
        </tr>"""
    metrics = []
    result = wily.commands.bulk.generate_table_row(
        filename, htmlname, metrics, nl_indent, mock_path
    )
    assert result == no_metrics_with_files

    metrics_with_files = """
        <tr>
            <th><a href="annotated_test.py.html">test.py</a></th>
            <td><a href="test.py_report.html">Report</a></td>
            <td><a href="test.py_metric1.html">metric1</a></td>
            <td><a href="test.py_metric2.html">metric2</a></td>
        </tr>"""
    metrics = ["metric1", "metric2"]
    result = wily.commands.bulk.generate_table_row(
        filename, htmlname, metrics, nl_indent, mock_path
    )
    assert result == metrics_with_files


def test_build_reports_empty():
    mock_path = mock.MagicMock()
    mock_exists = mock.MagicMock(return_value=False)
    mock_exists.exists = mock_exists
    mock_path.__truediv__.return_value = mock_exists
    mock.mock_open(mock=mock_exists)
    config = mock.Mock()
    mock_report = mock.Mock()
    mock_graph = mock.Mock()

    metrics = []
    files = ()
    result = wily.commands.bulk.build_reports(
        config,
        metrics,
        files,
        mock_path,
        cached=True,
        index_only=False,
        globals_only=False,
        changes_only=True,
    )
    assert len(result) == 1
    assert mock_path.__truediv__.call_count == 2
    mock_report.assert_not_called()
    mock_graph.assert_not_called()


def test_build_reports_files_no_metrics():
    mock_path = mock.MagicMock()
    mock_exists = mock.MagicMock(return_value=False)
    mock_exists.exists = mock_exists
    mock_path.__truediv__.return_value = mock_exists
    mock.mock_open(mock=mock_exists)
    config = mock.Mock()
    mock_report = mock.Mock()
    mock_graph = mock.Mock()
    with mock.patch("bulk_wily.report", mock_report), mock.patch(
        "bulk_wily.graph", mock_graph
    ):
        metrics = []
        files = (pathlib.Path("file1.py"), pathlib.Path("file2.py"))
        result = wily.commands.bulk.build_reports(
            config,
            metrics,
            files,
            mock_path,
            cached=True,
            index_only=False,
            globals_only=False,
            changes_only=True,
        )
        assert len(result) == 3
    assert mock_path.__truediv__.call_count == 8
    assert mock_report.call_count == 2
    assert mock_graph.call_count == 0


def test_build_reports_files_and_metrics():
    mock_path = mock.MagicMock()
    mock_exists = mock.MagicMock(return_value=False)
    mock_exists.exists = mock_exists
    mock_path.__truediv__.return_value = mock_exists
    mock.mock_open(mock=mock_exists)
    config = mock.Mock()
    mock_report = mock.Mock()
    mock_graph = mock.Mock()
    with mock.patch("bulk_wily.report", mock_report), mock.patch(
        "bulk_wily.graph", mock_graph
    ):
        metrics = ["metric1", "metric2"]
        files = (pathlib.Path("file1.py"), pathlib.Path("file2.py"))
        result = wily.commands.bulk.build_reports(
            config,
            metrics,
            files,
            mock_path,
            cached=True,
            index_only=False,
            globals_only=False,
            changes_only=True,
        )
        assert len(result) == 9
    assert mock_path.__truediv__.call_count == 20
    assert mock_report.call_count == 2
    assert mock_graph.call_count == 6


def test_build_reports_index_only():
    mock_path = mock.MagicMock()
    mock_exists = mock.MagicMock(return_value=False)
    mock_exists.exists = mock_exists
    mock_path.__truediv__.return_value = mock_exists
    mock.mock_open(mock=mock_exists)
    config = mock.Mock()
    mock_report = mock.Mock()
    mock_graph = mock.Mock()
    with mock.patch("bulk_wily.report", mock_report), mock.patch(
        "bulk_wily.graph", mock_graph
    ):
        metrics = ["metric1", "metric2"]
        files = (pathlib.Path("file1.py"), pathlib.Path("file2.py"))
        result = wily.commands.bulk.build_reports(
            config,
            metrics,
            files,
            mock_path,
            cached=True,
            index_only=True,
            globals_only=False,
            changes_only=True,
        )
        assert len(result) == 9
    assert mock_path.__truediv__.call_count == 20
    assert mock_report.call_count == 0
    assert mock_graph.call_count == 0


def test_build_reports_globals_only():
    mock_path = mock.MagicMock()
    mock_exists = mock.MagicMock(return_value=False)
    mock_exists.exists = mock_exists
    mock_path.__truediv__.return_value = mock_exists
    mock.mock_open(mock=mock_exists)
    config = mock.Mock()
    mock_report = mock.Mock()
    mock_graph = mock.Mock()
    with mock.patch("bulk_wily.report", mock_report), mock.patch(
        "bulk_wily.graph", mock_graph
    ):
        metrics = ["metric1", "metric2"]
        files = (pathlib.Path("file1.py"), pathlib.Path("file2.py"))
        result = wily.commands.bulk.build_reports(
            config,
            metrics,
            files,
            mock_path,
            cached=True,
            index_only=False,
            globals_only=True,
            changes_only=True,
        )
        assert len(result) == 9
    assert mock_path.__truediv__.call_count == 20
    assert mock_report.call_count == 0
    assert mock_graph.call_count == 2
