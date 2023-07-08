"""Quick and dirty global report generator for Wily."""

import pathlib
from time import time

start = time()

from git.repo import Repo

from wily.commands.graph import graph
from wily.commands.report import report
from wily.config import DEFAULT_CONFIG_PATH
from wily.config import load as load_config, WilyConfig
from wily.helper.custom_enums import ReportFormat
from wily.operators import ALL_OPERATORS


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
    metrics = []
    for name, operator in sorted(ALL_OPERATORS.items()):
        if len(operator.cls.metrics) == 0:
            metrics.append(name)
        else:
            for metric in operator.cls.metrics:
                metrics.append(metric.name)
    return metrics


metrics = list_metrics()

columns = ["<td><h3>Report</h3></td>"]
for metric in metrics:
    columns.append(f"<td><h3>{metric}</h3></td>")
nl_indent = "\n            "
header = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Wily Reports</title>
</head>
<body>
<table>
    <thead>
        <tr>
            <td><h3>Filename</h3></td>
            {nl_indent.join(columns)}
        </tr>
    </thead>
"""
footer = """</table>
</body>
</html>"""

path = pathlib.Path("reports/")
path.mkdir(exist_ok=True, parents=True)

config = load_config(DEFAULT_CONFIG_PATH)
files = get_all_tracked(config)


def build_reports(metrics):
    rows = []
    nl_indent = "\n            "
    total = len(files)
    for index, filepath in enumerate(files):
        filename = str(filepath)
        print(filename, f"{index + 1}/{total}")
        htmlname = str(filename).replace("\\", ".").replace("/", ".")
        output = f"{path}{htmlname}_report.html"
        new_output = pathlib.Path().cwd()
        new_output = new_output / pathlib.Path(output)
        report(
            config,
            filename,
            metrics,
            500,
            new_output,
            include_message=True,
            format=ReportFormat.HTML,
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
            graph(
                config,
                filename,
                (metric,),
                output=f"{path}{metric_name}",
                changes=True,
                text=False,
                aggregate=False,
                #plotlyjs="directory",
            )
    entries = "".join(rows)
    with open(path / "index.html", "w") as index:
        index.write(header)
        index.write(entries)
        index.write(footer)


build_reports(metrics)
print(f"{time() - start} secs")
