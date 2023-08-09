"""
Bulk report generator for wily.

Use wily to create multiple reports and graphs for a Python project stored in
Git. Generate an index page linking to HTML reports and graphs, if they exist.
Doing so is faster and results in smaller files than naively running wily
for each separate file.
"""
from __future__ import annotations

import pathlib
from string import Template
from time import time
from typing import Optional

import click
from git.repo import Repo
from wily.defaults import DEFAULT_GRID_STYLE

from wily import logger
from wily.commands.graph import graph
from wily.commands.report import report
from wily.config import DEFAULT_CONFIG_PATH, WilyConfig
from wily.config import load as load_config
from wily.helper.custom_enums import ReportFormat
from wily.operators import ALL_OPERATORS

logger.setLevel("INFO")
start = time()


def get_all_tracked(config: WilyConfig) -> list[pathlib.Path]:
    """Get all tracked files that ever existed in git repo."""
    # ToDo: check whether using graph's method is better
    repo = Repo(config.path)
    path_log = repo.git.execute(
        ["git", "log", "--name-only", "--pretty=format:", "--name-only"]
    )
    assert isinstance(path_log, str)
    path_list = path_log.split("\n")
    paths = [name for name in path_list if name.endswith(".py")]
    paths = sorted(set(paths))
    return [pathlib.Path(path) for path in paths]


def list_metrics() -> list[str]:
    """List all known metrics (excluding rank)."""
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
    """Get headers with metric names for the index.html table."""
    columns = ["<th><h3>Filename</h3></th>", "<th><h3>Report</h3></th>"]
    for metric in metrics:
        columns.append(f"<th><h3>{metric}</h3></th>")
    nl_indent = "\n            "
    return nl_indent.join(columns)


def build_reports(
    config: WilyConfig,
    metrics: list[str],
    files: list[pathlib.Path],
    path: pathlib.Path,
    cached: bool = True,
    index_only: bool = False,
    globals_only: bool = False,
    changes_only: bool = True,
) -> list[pathlib.Path]:
    """Build bulk reports.

    This generates an index page that contains links to annotated source files,
    reports and metric graphs. Depending on options, also creates the HTML reports
    and graphs.

    Args:
        config: The `WilyConfig` that will be passed to `graph()` and `report()`.
        metrics: A lisf of metric names for graph generation.
        files: A list of `pathlib.Path` of the files for which to generate reports and graphs.
        path: Output directory where files will be written.
        cached: Whether to use caching to speed up reading JSON from wily's cache.
        index_only: Only generate the index page, with links to existing files.
        globals_only: Only generate the global graphs and the index page.
        changes_only: Only show revisions with changes.

    Returns:
        A list of `pathlib.Path` files that would be created.

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
                "",
                (metric,),
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
                    filename,
                    (metric,),
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
    templates_dir = (pathlib.Path(__file__).parents[0] / "wily" / "templates").resolve()
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
    """Link to a metric/report file if it exists, otherwise just output the name.

    Args:
        columns: A list of strings that will be appended to.
        filename: The name of the HTML file to link to, if it exists.
        name: The name of the metric (or "Report") to include.
        path: The output directory where files should be searched for.

    """
    if (path / filename).exists():
        columns.append(f'<td><a href="{filename}">{name}</a></td>')
    else:
        columns.append(f"<td>{name}</td>")


def generate_global_row(metrics: list[str], nl_indent: str, path: pathlib.Path) -> str:
    """Generate the "global" table row containing metrics.

    Args:
        metrics: A list of metric names.
        nl_indent: A string containing a new-line and indentation to format the HTML.
        path: The output directory where files should be searched for.

    Returns:
        A string representing an HTML table row containing metric names (which
        are links to global HTML graphs if the corresponding file exists).

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
    """Generate a table row containing the file and metrics.

    Args:
        filename: The source code filename, with path.
        htmlname: The source code filename, with path and path separators replaced by dots.
        metrics: A list of metrics for which to generate links/labels.
        nl_indent: A string containing a new-line and indentation to format the HTML.
        path: The output directory where files should be searched for.


    Returns:
        A string representing an HTML table row containing metric names (which
        are links to HTML graphs if the corresponding file exists).
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


@click.group
def main() -> None:
    """Bulk operations for wily."""


@main.command(help="Build the bulk report.")
@click.argument(
    "paths",
    nargs=-1,
    type=click.Path(resolve_path=False, path_type=pathlib.Path),
)
@click.option(
    "output_path",
    "-o",
    "--output",
    type=click.Path(resolve_path=False, path_type=pathlib.Path),
    help="Output directory",
)
@click.option(
    "-c",
    "--cache/--no-cache",
    default=True,
    help="Use caching",
)
@click.option(
    "-i",
    "--index/--full",
    default=False,
    help="Only build index.html",
)
@click.option(
    "-g",
    "--globals-only/--per-file",
    default=False,
    help="Only create metric graphs for all files",
)
@click.option(
    "-m", "--metrics", help="Comma-separated metrics to build bulk reports with"
)
@click.option(
    "-c",
    "--changes/--all",
    default=True,
    help="Only show revisions that have changes",
)
@click.pass_context
def build(
    ctx: click.Context,
    paths: tuple[pathlib.Path],
    output_path: Optional[pathlib.Path],
    cache: bool,
    index: bool,
    globals_only: bool,
    metrics: str,
    changes: bool,
) -> None:
    """Build the bulk reports."""
    if output_path is None:
        output_path = pathlib.Path("reports/")
    output_path.mkdir(exist_ok=True, parents=True)
    config = load_config(DEFAULT_CONFIG_PATH)
    files = paths if paths else get_all_tracked(config)
    metrics = metrics.split(",") if metrics else list_metrics()
    build_reports(
        config,
        metrics,
        files,
        output_path,
        cached=cache,
        index_only=index,
        globals_only=globals_only,
        changes_only=changes,
    )
    logger.info(f"Total time: {time() - start} secs")


@main.command(help="Erase the bulk report files.")
@click.argument(
    "paths",
    nargs=-1,
    type=click.Path(resolve_path=False, path_type=pathlib.Path),
)
@click.option(
    "output_path",
    "-o",
    "--output",
    type=click.Path(resolve_path=False, path_type=pathlib.Path),
    help="Output directory to clean",
)
@click.option("-m", "--metrics", help="Comma-separated metrics to clean bulk reports")
@click.pass_context
def clean(
    ctx: click.Context,
    paths: tuple[pathlib.Path],
    output_path: Optional[pathlib.Path],
    metrics: str,
) -> None:
    """Erase the bulk report files."""
    if output_path is None:
        output_path = pathlib.Path("reports/")
    config = load_config(DEFAULT_CONFIG_PATH)
    files = paths if paths else get_all_tracked(config)
    metrics = metrics.split(",") if metrics else list_metrics()
    files_to_clean = build_reports(config, metrics, files, output_path, index_only=True)
    for file in files_to_clean:
        to_delete = pathlib.Path(file)
        to_delete.unlink(missing_ok=True)
    logger.info(f"Total time: {time() - start} secs")


if __name__ == "__main__":
    main()
