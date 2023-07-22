"""Quick and dirty global report generator for Wily."""

import pathlib
from string import Template
from time import time

import click
from git.repo import Repo

from wily.commands.graph import graph
from wily.commands.report import report
from wily.config import DEFAULT_CONFIG_PATH, WilyConfig
from wily.config import load as load_config
from wily.helper.custom_enums import ReportFormat
from wily.operators import ALL_OPERATORS

start = time()


def get_all_tracked(config: WilyConfig) -> list[pathlib.Path]:
    """Get all tracked files that ever existed in git repo."""
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
    """List all known metrics."""
    metrics = []
    for name, operator in sorted(ALL_OPERATORS.items()):
        if len(operator.cls.metrics) == 0:
            metrics.append(name)
        else:
            for metric in operator.cls.metrics:
                if metric.name != "rank":
                    metrics.append(metric.name)
    return metrics


def get_headers(metrics: list[str]) -> str:
    """Get headers for the index.html table."""
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
) -> list[pathlib.Path]:
    """Build bulk reports."""
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
                changes=True,
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
            print(filename, f"{index + 1}/{total}")
            report(
                config,
                filename,
                metrics,
                500,
                new_output,
                include_message=True,
                format=ReportFormat.HTML,
                cached=cached,
                changes_only=True,
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
                    changes=True,
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

    print(f"Globals time: {globals_time} secs")
    print(f"Report and metrics time: {time() - start_metrics_report} secs")

    return created_files


def generate_global_row(metrics: list[str], nl_indent: str, path: pathlib.Path) -> str:
    """Generate the "global" table row containing metrics."""
    columns = ["    <td></td>"]
    for metric in metrics:
        html_global = f"global_{metric}.html"
        if (path / html_global).exists():
            columns.append(f'<td><a href="{html_global}">{metric}</a></td>')
        else:
            columns.append(f"<td>{metric}</td>")
    row = f"""
        <tr>
            <th>global</th>
        {nl_indent.join(columns)}
        </tr>"""
    return row


def generate_table_row(
    filename: str, htmlname: str, metrics: list[str], nl_indent: str, path: pathlib.Path
) -> str:
    """Generate a table row containing the file and metrics."""
    html_report = f"{htmlname}_report.html"
    if (path / html_report).exists():
        report_label = f'<td><a href="{html_report}">Report</a></td>'
    else:
        report_label = "<td>Report</td>"
    columns = [report_label]
    for metric in metrics:
        html_metric = f"{htmlname}_{metric}.html"
        if (path / html_metric).exists():
            columns.append(f'<td><a href="{htmlname}_{metric}.html">{metric}</a></td>')
        else:
            columns.append(f"<td>{metric}</td>")
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
    """Group commands."""


@main.command(help="Build the bulk report.")
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
@click.pass_context
def build(ctx: click.Context, cache: bool, index: bool, globals_only: bool) -> None:
    """Build the bulk reports."""
    path = pathlib.Path("reports/")
    path.mkdir(exist_ok=True, parents=True)
    config = load_config(DEFAULT_CONFIG_PATH)
    files = get_all_tracked(config)
    metrics = list_metrics()
    build_reports(
        config,
        metrics,
        files,
        path,
        cached=cache,
        index_only=index,
        globals_only=globals_only,
    )
    print(f"Total time: {time() - start} secs")


@main.command(help="Erase the bulk report files.")
@click.pass_context
def clean(ctx: click.Context) -> None:
    """Erase the bulk report files."""
    path = pathlib.Path("reports/")
    config = load_config(DEFAULT_CONFIG_PATH)
    files = get_all_tracked(config)
    metrics = list_metrics()
    files_to_clean = build_reports(config, metrics, files, path, index_only=True)
    for file in files_to_clean:
        to_delete = pathlib.Path(file)
        to_delete.unlink(missing_ok=True)
    print(f"Total time: {time() - start} secs")


if __name__ == "__main__":
    main()
