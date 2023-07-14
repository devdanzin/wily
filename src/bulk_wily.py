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


def get_all_tracked(config: WilyConfig):
    """Get all tracked files that ever existed in git repo."""
    repo = Repo(config.path)
    paths = repo.git.execute(
        ["git", "log", "--name-only", "--pretty=format:", "--name-only"]
    ).split("\n")
    paths = [name for name in paths if name.endswith(".py")]
    paths = sorted(set(paths))
    return [pathlib.Path(path) for path in paths]


def list_metrics():
    """List all known metrics."""
    metrics = []
    for name, operator in sorted(ALL_OPERATORS.items()):
        if len(operator.cls.metrics) == 0:
            metrics.append(name)
        else:
            for metric in operator.cls.metrics:
                metrics.append(metric.name)
    return metrics


def get_headers(metrics):
    """Get headers for the index.html table."""
    columns = ["<td><h3>Filename</h3></td>", "<td><h3>Report</h3></td>"]
    for metric in metrics:
        columns.append(f"<td><h3>{metric}</h3></td>")
    nl_indent = "\n            "
    return nl_indent.join(columns)


def build_reports(config, metrics, files, path, cached=True, index_only=False):
    """Build bulk reports."""
    rows = []
    created_files = [path / "index.html"]
    nl_indent = "\n            "
    total = len(files)
    columns = ["    <td></td>"]
    for metric in metrics:
        columns.append(f'<td><a href="global_{metric}.html">{metric}</a></td>')
    row = f"""
        <tr>
            <td><b>global</b></td>
        {nl_indent.join(columns)}
        </tr>"""
    rows.append(row)
    start_global = time()

    for metric in metrics:
        metric_name = f"global_{metric}.html"
        metric_filename = f"{path / metric_name}"
        created_files.append(metric_filename)
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
    globals_time = time() - start_global

    start_metrics_report = time()
    for index, filepath in enumerate(files):
        filename = str(filepath)
        htmlname = str(filename).replace("\\", ".").replace("/", ".")
        output = f"{path / htmlname}_report.html"
        new_output = pathlib.Path().cwd()
        new_output = new_output / pathlib.Path(output)
        created_files.append(new_output)
        if not index_only:
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
        columns = [f'<td><a href="{htmlname}_report.html">Report</a></td>']
        for metric in metrics:
            columns.append(f'<td><a href="{htmlname}_{metric}.html">{metric}</a></td>')
        row = f"""
        <tr>
            <td><b>{filename}</b></td>
            {nl_indent.join(columns)}
        </tr>"""
        rows.append(row)

        for metric in metrics:
            metric_name = f"{htmlname}_{metric}.html"
            metric_filename = f"{path / metric_name}"
            created_files.append(metric_filename)
            if not index_only:
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

    entries = "".join(rows)
    table_headers = get_headers(metrics)
    templates_dir = (pathlib.Path(__file__).parents[0] / "wily" / "templates").resolve()
    report_template = Template((templates_dir / "bulk_template.html").read_text())
    report_template = report_template.safe_substitute(
        headers=table_headers, content=entries
    )

    with (path / "index.html").open("w", errors="xmlcharrefreplace") as output:
        output.write(report_template)

    print(f"Globals time: {globals_time} secs")
    print(f"Report and metrics time: {time() - start_metrics_report} secs")

    return created_files


@click.group
def main():
    """Group commands."""


@main.command(help="Build the bulk report.")
@click.option(
    "-c",
    "--cache/--no-cache",
    default=False,
    help="Use caching",
)
@click.option(
    "-i",
    "--index/--full",
    default=False,
    help="Only build index.html",
)
@click.pass_context
def build(ctx, cache, index):
    """Build the bulk reports."""
    path = pathlib.Path("reports/")
    path.mkdir(exist_ok=True, parents=True)
    config = load_config(DEFAULT_CONFIG_PATH)
    files = get_all_tracked(config)
    metrics = list_metrics()
    build_reports(config, metrics, files, path, cached=cache, index_only=index)
    print(f"Total time: {time() - start} secs")


@main.command(help="Erase the bulk report files.")
@click.pass_context
def clean(ctx):
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
