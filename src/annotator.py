"""Annotate source code with metrics."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from string import Template
from sys import exit
from typing import Any

import click
import git
from git import Repo
from pygments import highlight
from pygments.formatters import HtmlFormatter, TerminalFormatter
from pygments.lexers import PythonLexer

from wily import logger
from wily.archivers import resolve_archiver
from wily.config import DEFAULT_CONFIG_PATH
from wily.config import load as load_config
from wily.state import IndexedRevision, State

logger.setLevel(logging.INFO)


class AnnotatedHTMLFormatter(HtmlFormatter):
    """Annotate and color source code with metric values as HTML."""

    halstead_names = "h1", "h2", "N1", "N2", "vocabulary", "length", "volume", "effort", "difficulty"

    def __init__(
        self, metrics: list[dict[int, tuple[str, str]]], **options: Any
    ) -> None:
        """Set up the formatter instance with metrics."""
        super().__init__(**options)
        self.metrics = metrics
        spans = []
        for name, val in zip(self.halstead_names, ("---",) * 6 + ("-------",) * 3):
            spans.append(f'<span class="{name}_val">{val} </span>')
        self.empty_halstead_spans = "".join(spans)

    def wrap(self, source) -> None:
        """Wrap the ``source`` in custom generators."""
        output = source
        output = self.annotate_lines(output)
        if self.wrapcode:
            output = self._wrap_code(output)

        output = self._wrap_pre(output)

        return output

    def annotate_lines(self, tokensource):
        """Add metric annotations from self.metrics."""
        for i, (_t, value) in enumerate(tokensource):
            empty_halstead = (
                '<div class="halstead" style="background-color: #ffffff; width: 100%;">'
                f'{self.empty_halstead_spans}| {value}</div>'
            )
            if not self.metrics[0]:
                yield 1, value
            if i in self.metrics[0]:
                if self.metrics[0][i][1][1] == "-":  # Just use function values for now
                    c = "#ffffff"
                else:
                    val = int(self.metrics[0][i][1])
                    red = max(0, min(255, round(0.04 * 255 * (val - 1))))
                    green = max(0, min(255, round(0.04 * 255 * (50 - val + 1))))
                    blue = 0
                    c = f"rgba{(red, green, blue, 0.75)}"
                if i not in self.metrics[1] or self.metrics[1][i][1][1] == "-":
                    halstead = empty_halstead
                else:
                    val = int(self.metrics[1][i][1])
                    red = max(0, min(255, round(0.04 * 255 * (val - 1))))
                    green = max(0, min(255, round(0.04 * 255 * (50 - val + 1))))
                    blue = 0
                    h = f"rgba{(red, green, blue, 0.75)}"
                    spans = []
                    for name, val in zip(self.halstead_names, self.metrics[1][i]):
                        spans.append(f'<span class="{name}_val">{val} </span>')
                    halstead = (
                        f'<div class="halstead" style="background-color: {h}; width: 100%;">'
                        f"{''.join(spans)}| {value}</div>"
                    )
                yield 1, (
                    f'<div class="cyclomatic" style="background-color: {c}; width: 100%;">'
                    '<span style="background-color: #ffffff;">'
                    f'{" ".join(self.metrics[0][i])} |</span> {value}</div>'
                    f"{halstead}"
                )
            else:
                yield 1, (
                    '<div class="cyclomatic" style="background-color: #ffffff; width: 100%;">'
                    '<span style="background-color: #ffffff;">'
                    f'{" ".join(("--", "--"))} |</span> {value}</div>'
                    f"{empty_halstead}"
                )


class AnnotatedTerminalFormatter(TerminalFormatter):
    """Annotate and source code with metric values to print to terminal."""

    def __init__(self, metrics: dict[int, tuple[str, str]], **options: Any) -> None:
        """Set up the formatter instance with metrics."""
        super().__init__(**options)
        self.metrics = metrics

    def _write_lineno(self, outfile) -> None:
        """Write line numbers and metric annotations."""
        self._lineno += 1
        metric_values = " ".join(self.metrics.get(self._lineno - 1, ("--", "--")))
        outfile.write(
            f"%s%04d: {metric_values} |"
            % (self._lineno != 1 and "\n" or "", self._lineno)
        )


def last_line(details: dict) -> int:
    """Get the last line from a series of detailed metric entries."""
    lineends = []
    for _name, detail in details.items():
        endline: int = detail.get("endline", 0)
        lineends.append(endline)
    return max(lineends or [0])


def map_cyclomatic_lines(details: dict) -> dict[int, tuple[str, str]]:
    """Map complexity metric values to lines, for functions/methods and classes."""
    last = last_line(details)
    lines = {i: ("--", "--") for i in range(last + 1)}
    for _name, detail in details.items():
        if "is_method" in detail:
            for line in range(detail["lineno"] - 1, detail["endline"]):
                lines[line] = (lines[line][0], f"{detail['complexity']:02d}")
        else:
            for line in range(detail["lineno"] - 1, detail["endline"]):
                lines[line] = (f"{detail['complexity']:02d}", lines[line][1])
    return lines


def map_halstead_lines(details: dict) -> dict[int, tuple[str, ...]]:
    """Map Halstead metric values to lines, for functions."""
    last = last_line(details)
    lines = {i: ("---",) * 6 + ("-------",) * 3 for i in range(last + 1)}
    for _name, detail in details.items():
        if "lineno" not in detail:
            continue
        for line in range(detail["lineno"] - 1, detail["endline"]):
            lines[line] = (
                f"{detail['h1']:03d}",
                f"{detail['h2']:03d}",
                f"{detail['N1']:03d}",
                f"{detail['N2']:03d}",
                f"{detail['vocabulary']:03d}",
                f"{detail['length']:03d}",
                f"{detail['volume']:07.2f}",
                f"{detail['effort']:07.2f}",
                f"{detail['difficulty']:07.2f}",
            )
    return lines


def add_halstead_lineno(halstead: dict, cyclomatic: dict):
    """Map line numbers from the cyclomatic data to the halstead data."""
    for filename, data in halstead.items():
        if "detailed" not in data:
            continue
        for function, details in data["detailed"].items():
            if function not in cyclomatic[filename]["detailed"]:
                continue
            details["lineno"] = cyclomatic[filename]["detailed"][function]["lineno"]
            details["endline"] = cyclomatic[filename]["detailed"][function]["endline"]


def bulk_annotate() -> None:
    """Annotate all Python files found in the index's revisions."""
    config = load_config(DEFAULT_CONFIG_PATH)
    state = State(config)
    latest = {}
    for rev_key in state.index[state.default_archiver].revision_keys:
        rev_data = Path(config.cache_path) / "git" / f"{rev_key}.json"
        as_dict = json.loads(rev_data.read_text())
        cyclomatic = as_dict["operator_data"]["cyclomatic"]
        for filename, _data in cyclomatic.items():
            if filename.endswith(".py") and filename not in latest:
                latest[filename] = rev_key
    for filename, rev_key in latest.items():
        try:
            annotate_revision(format="HTML", revision_index=rev_key, path=filename)
        except FileNotFoundError:
            logger.error(
                f"Path {filename} not found in current state of git repository."
            )


def annotate_revision(
    format: str = "HTML", revision_index: str = "", path: str = ""
) -> None:
    """Generate annotated files from detailed metric data in a revision."""
    config = load_config(DEFAULT_CONFIG_PATH)
    state = State(config)
    repo = Repo(config.path)

    target_revision: IndexedRevision
    # TODO: try to fetch revision_index from index before resolving in repo.
    if not revision_index:
        commit = repo.rev_parse("HEAD")
    else:
        try:
            commit = repo.rev_parse(revision_index)
        except git.BadName:
            logger.error(
                f"Revision {revision_index} not found in current git repository."
            )
            exit(1)
        rev = (
            resolve_archiver(state.default_archiver)
            .archiver_cls(config)
            .find(commit.hexsha)
        )
        logger.debug(f"Resolved {revision_index} to {rev.key} ({rev.message})")
    try:
        target_revision = state.index[state.default_archiver][commit.hexsha]
    except KeyError:
        logger.error(
            f"Revision {revision_index or 'HEAD'} is not in the cache, make sure you have run wily build."
        )
        exit(1)
    rev_key = target_revision.revision.key
    rev_data = Path(config.cache_path) / "git" / f"{rev_key}.json"
    as_dict = json.loads(rev_data.read_text())
    cyclomatic = as_dict["operator_data"]["cyclomatic"]
    halstead = as_dict["operator_data"]["halstead"]
    add_halstead_lineno(halstead, cyclomatic)
    if path:
        if path not in cyclomatic:
            logger.error(f"Data for file {path} not found on revision {rev_key}.")
            exit(1)
        else:
            py_files = [path]
    else:
        py_files = [key for key in cyclomatic.keys() if key.endswith(".py")]
        if not py_files:
            logger.error(
                f"Revision {rev_key} has no files with Cyclomatic Complexity data."
            )
            exit(1)
    if format.lower() == "html":
        logger.info(
            f"Saving annotated source code for {', '.join(py_files)} at rev {rev_key[:7]}."
        )
    elif format.lower() == "console":
        logger.info(
            f"Showing annotated source code for {', '.join(py_files)} at rev {rev_key[:7]}."
        )
    for filename in py_files:
        diff = commit.diff(None, filename)
        outdated = False
        if diff:
            if diff[0].change_type in ("M",):
                outdated = True
        path_ = Path(filename)
        if path_.exists() and not outdated:
            code = path_.read_text()
        else:
            git_filename = filename.replace("\\", "/")
            code = repo.git.execute(
                ["git", "show", f"{rev_key}:{git_filename}"],
                as_process=False,
                stdout_as_string=True,
            )
        details = cyclomatic[filename]["detailed"]
        metrics = [
            map_cyclomatic_lines(details),
            map_halstead_lines(halstead[filename]["detailed"]),
        ]
        if format.lower() == "html":
            generate_annotated_html(
                code, filename, metrics, target_revision.revision.key
            )
        elif format.lower() == "console":
            print_annotated_source(code, metrics[0])


def print_annotated_source(code: str, metrics: dict[int, tuple[str, str]]) -> None:
    """Print source annotated with metric to terminal."""
    result = highlight(
        code,
        PythonLexer(),
        AnnotatedTerminalFormatter(
            linenos=True,
            metrics=metrics,
        ),
    )
    print(result)


def generate_annotated_html(
    code: str, filename: str, metrics: list[dict[int, tuple[str, str]]], key: str
) -> None:
    """Generate an annotated HTML file from source code and metric data."""
    formatter = AnnotatedHTMLFormatter(
        title=f"CC for {filename} at {key[:7]}",
        lineanchors="line",
        anchorlinenos=True,
        filename=filename,
        linenos=True,
        full=False,
        metrics=metrics,
    )
    result = highlight(
        code,
        PythonLexer(),
        formatter=formatter,
    )
    reports_dir = Path(__file__).parents[1] / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    htmlname = filename.replace("\\", ".").replace("/", ".")
    output = reports_dir / f"annotated_{htmlname}.html"
    logger.info(f"Saving {filename} annotated source code to {output}.")

    templates_dir = (Path(__file__).parent / "wily" / "templates").resolve()
    report_template = Template((templates_dir / "annotated_template.html").read_text())
    result = report_template.safe_substitute(filename=filename, annotated=result)
    with output.open("w", errors="xmlcharrefreplace") as html:
        html.write(result)
    css_output = reports_dir / "annotated.css"
    if not css_output.exists():
        with css_output.open("w") as css:
            css.write(formatter.get_style_defs())


@click.command(help="Annotate source files with Cyclomatic Complexity values.")
@click.option(
    "-f",
    "--format",
    default="CONSOLE",
    help="Save HTML or print to CONSOLE",
    type=click.STRING,
)
@click.option(
    "-r",
    "--revision",
    default="HEAD",
    help="Annotate with metric values from specific revision",
    type=click.STRING,
)
def run(format: str, revision: str) -> None:
    """Generate annotated source."""
    if format.lower() not in ("html", "console"):
        logger.error(f"Format must be HTML or CONSOLE, not {format}.")
        exit(1)

    annotate_revision(format=format, revision_index=revision)


if __name__ == "__main__":
    bulk_annotate()
