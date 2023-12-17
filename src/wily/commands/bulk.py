"""
Bulk report generator for wily.

Use wily to create multiple reports and graphs for a Python project stored in
Git. Generate an index page linking to HTML reports and graphs, if they exist.
Doing so is faster and results in smaller files than naively running wily
for each separate file.
"""
import pathlib
from string import Template
from time import time

from git.repo import Repo

from wily import logger
from wily.commands.graph import graph
from wily.commands.report import report
from wily.config import WilyConfig
from wily.defaults import DEFAULT_GRID_STYLE
from wily.helper.custom_enums import ReportFormat
from wily.operators import ALL_OPERATORS, resolve_metric

start = time()


def get_all_tracked(config: WilyConfig) -> tuple[pathlib.Path, ...]:
    """
    Get all tracked files that ever existed in git repo.

    :param config: The config from which to get the repository path.
    :return: A sorted list of unique Paths of tracked Python files.
    """
    # ToDo: check whether using graph's method is better
    repo = Repo(config.path)
    path_log = str(
        repo.git.execute(
            ["git", "log", "--name-only", "--pretty=format:", "--name-only"]
        )
    )
    path_list = path_log.split("\n")
    paths = [name for name in path_list if name.endswith(".py")]
    paths = sorted(set(paths))
    return tuple(pathlib.Path(path) for path in paths)


def list_all_metrics() -> list[str]:
    """
    List all known metrics (excluding rank).

    :return: A list of all known metric names
    """
    metrics = []
    for name, operator in sorted(ALL_OPERATORS.items()):
        if len(operator.operator_cls.metrics) == 0:
            metrics.append(name)
        else:
            for metric in operator.operator_cls.metrics:
                if metric.name != "rank":
                    metrics.append(metric.name)
    return metrics


def get_headers(metrics: list[str]) -> str:
    """
    Get headers with metric names for the index.html table.

    :param metrics: A list of metric names.
    :return: The HTML headers for the bulk report table.
    """
    columns = ["<th><h3>Filename</h3></th>", "<th><h3>Report</h3></th>"]
    for metric in metrics:
        columns.append(
            f'<th><h3 title="{resolve_metric(metric).description}">{metric}</h3></th>'
        )
    nl_indent = "\n            "
    return nl_indent.join(columns)


def build_reports(
    config: WilyConfig,
    metrics: list[str],
    files: tuple[pathlib.Path, ...],
    path: pathlib.Path,
    cached: bool = True,
    index_only: bool = False,
    globals_only: bool = False,
    changes_only: bool = True,
) -> list[pathlib.Path]:
    """
    Build bulk reports.

    This generates an index page that contains links to annotated source files,
    reports and metric graphs. Depending on options, also creates the HTML reports
    and graphs.

    :param config: The `WilyConfig` that will be passed to `graph()` and `report()`.
    :param metrics: A lisf of metric names for graph generation.
    :param files: A list of `pathlib.Path` of the files for which to generate reports and graphs.
    :param path: Output directory where files will be written.
    :param cached: Whether to use caching to speed up reading JSON from wily's cache.
    :param index_only: Only generate the index page, with links to existing files.
    :param globals_only: Only generate the global graphs and the index page.
    :param changes_only: Only show revisions with changes.

    :return: A list of `pathlib.Path` files that would be created.
    """
    rows = []
    created_files = [path / "index.html"]
    nl_indent = "\n            "
    total = len(files)

    start_global = time()

    for metric in metrics:
        metric_name = f"global_{metric}.html"
        metric_file = path / metric_name
        metric_filename = str(metric_file)
        created_files.append(metric_file)
        if not index_only:
            graph(
                config,
                ("",),
                metric,
                output=metric_filename,
                changes=changes_only,
                text=False,
                aggregate=False,
                plotlyjs="directory",
                cached=cached,
            )
    row = generate_global_row(metrics, nl_indent, path)
    rows.append(row)
    globals_time = time() - start_global

    start_metrics_report = time()
    for index, filepath in enumerate(files):
        filename = str(filepath)
        htmlname = str(filename).replace("\\", ".").replace("/", ".")
        output = f"{path / htmlname}_report.html"
        new_output = pathlib.Path().cwd()
        new_output = new_output / pathlib.Path(output)
        created_files.append(new_output)
        if not index_only and not globals_only:
            logger.info(f"{filename} {index + 1}/{total}")
            report(
                config,
                filename,
                metrics,
                500,
                new_output,
                console_format=DEFAULT_GRID_STYLE,
                include_message=True,
                format=ReportFormat.HTML,
                cached=cached,
                changes_only=changes_only,
            )

        for metric in metrics:
            metric_name = f"{htmlname}_{metric}.html"
            metric_file = path / metric_name
            metric_filename = str(metric_file)
            created_files.append(metric_file)
            if not index_only and not globals_only:
                graph(
                    config,
                    (filename,),
                    metric,
                    output=metric_filename,
                    changes=changes_only,
                    text=False,
                    aggregate=False,
                    plotlyjs="directory",
                    cached=cached,
                )

        row = generate_table_row(filename, htmlname, metrics, nl_indent, path)
        rows.append(row)

    entries = "".join(rows)
    table_headers = get_headers(metrics)
    templates_dir = (pathlib.Path(__file__).parents[1] / "templates").resolve()
    report_template = Template((templates_dir / "bulk_template.html").read_text())
    report_result = report_template.safe_substitute(
        headers=table_headers, content=entries
    )

    with (path / "index.html").open("w", errors="xmlcharrefreplace") as index_output:
        index_output.write(report_result)

    logger.info(f"Globals time: {globals_time} secs")
    logger.info(f"Report and metrics time: {time() - start_metrics_report} secs")

    return created_files


def link_if_exists(
    columns: list[str], filename: str, name: str, path: pathlib.Path
) -> None:
    """
    Link to a metric/report file if it exists, otherwise just output the name.

    :param columns: A list of strings that will be appended to.
    :param filename: The name of the HTML file to link to, if it exists.
    :param name: The name of the metric (or "Report") to include.
    :param path: The output directory where files should be searched for.
    """
    if (path / filename).exists():
        columns.append(f'<td><a href="{filename}">{name}</a></td>')
    else:
        columns.append(f"<td>{name}</td>")


def generate_global_row(metrics: list[str], nl_indent: str, path: pathlib.Path) -> str:
    """
    Generate the "global" table row containing metrics.

    :param metrics: A list of metric names.
    :param nl_indent: A string containing a new-line and indentation to format the HTML.
    :param path: The output directory where files should be searched for.

    :return: A string representing an HTML table row containing metric names/links.
    """
    columns = ["    <td></td>"]
    for metric in metrics:
        html_global = f"global_{metric}.html"
        link_if_exists(columns, html_global, metric, path)
    row = f"""
        <tr>
            <th>global</th>
        {nl_indent.join(columns)}
        </tr>"""
    return row


def generate_table_row(
    filename: str, htmlname: str, metrics: list[str], nl_indent: str, path: pathlib.Path
) -> str:
    """
    Generate a table row containing the file and metrics.

    :param filename: The source code filename, with path.
    :param htmlname: The source code filename, with path and path separators replaced by dots.
    :param metrics: A list of metrics for which to generate links/labels.
    :param nl_indent: A string containing a new-line and indentation to format the HTML.
    :param path: The output directory where files should be searched for.

    :return: A string representing an HTML table row containing metric names/links
    """
    columns: list[str] = []
    html_report = f"{htmlname}_report.html"
    link_if_exists(columns, html_report, "Report", path)
    for metric in metrics:
        html_metric = f"{htmlname}_{metric}.html"
        link_if_exists(columns, html_metric, metric, path)
    filename_or_link = filename
    annotated_path = pathlib.Path(f"annotated_{htmlname}.html")
    if (path / annotated_path).exists():
        filename_or_link = f'<a href="{annotated_path}">{filename}</a>'
    row = f"""
        <tr>
            <th>{filename_or_link}</th>
            {nl_indent.join(columns)}
        </tr>"""
    return row
