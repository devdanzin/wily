"""Annotate source code with metrics."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from sys import exit

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

    def __init__(self, metrics: dict[int, list[str]] | None = None, **options) -> None:
        """Set up the formatter instance with metrics."""
        super().__init__(**options)
        self.metrics = metrics

    def wrap(self, source):
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
            if not self.metrics:
                yield 1, value
            if i in self.metrics:
                if self.metrics[i][1] == "--":  # Just use function values for now
                    c = "#ffffff"
                else:
                    val = int(self.metrics[i][1])
                    red = max(0, min(255, round(0.02 * 255 * (val - 1))))
                    green = max(0, min(255, round(0.02 * 255 * (50 - val + 1))))
                    blue = 0
                    c = f"rgba{(red, green, blue, 0.75)}"
                yield 1, (
                    f'<div style="background-color: {c}; width: 100%%;">'
                    '<span style="background-color: #ffffff;">'
                    f'{" ".join(self.metrics[i])} |</span> {value}</div>'
                )
            else:
                yield 1, value


class AnnotatedTerminalFormatter(TerminalFormatter):
    """Annotate and source code with metric values to print to terminal."""

    def __init__(self, metrics=None, **options):
        """Set up the formatter instance with metrics."""
        super().__init__(**options)
        self.metrics = metrics

    def _write_lineno(self, outfile):
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
        lineends.append(detail["endline"])
    return max(lineends)


def map_lines(details: dict) -> dict[int, list[str]]:
    """Map metric values to lines, for functions/methods and classes."""
    last = last_line(details)
    lines = {i: ["--", "--"] for i in range(last + 1)}
    for _name, detail in details.items():
        if "is_method" in detail:
            for line in range(detail["lineno"] - 1, detail["endline"]):
                lines[line] = [lines[line][0], f"{detail['complexity']:02d}"]
        else:
            for line in range(detail["lineno"] - 1, detail["endline"]):
                lines[line] = [f"{detail['complexity']:02d}", lines[line][1]]
    return lines


def annotate_revision(format: str = "HTML", revision_index: str = "") -> None:
    """Generate annotated files from detailed metric data in a revision."""
    config = load_config(DEFAULT_CONFIG_PATH)
    state = State(config)
    repo = Repo(config.path)

    target_revision: IndexedRevision
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
        rev = resolve_archiver(state.default_archiver).cls(config).find(commit.hexsha)
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
    py_files = [
        key
        for key in as_dict["operator_data"]["cyclomatic"].keys()
        if key.endswith(".py")
    ]
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
        if diff:
            if diff[0].change_type in ("M",):
                logger.error(
                    f"Changes found in {filename} since revision {rev_key[:7]}. Line numbers might be wrong."
                )
        details = as_dict["operator_data"]["cyclomatic"][filename]["detailed"]
        path = Path(filename)
        code = path.read_text()
        metrics = map_lines(details)
        if format.lower() == "html":
            generate_annotated_html(
                code, filename, metrics, target_revision.revision.key
            )
        elif format.lower() == "console":
            print_annotated_source(code, metrics)


def print_annotated_source(code: str, metrics: dict[int, list[str]]):
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
    code: str, filename: str, metrics: dict[int, list[str]], key: str
):
    """Generate an annotated HTML file from source code and metric data."""
    result = highlight(
        code,
        PythonLexer(),
        AnnotatedHTMLFormatter(
            title=f"CC for {filename} at {key[:7]}",
            lineanchors="line",
            anchorlinenos=True,
            filename=filename,
            linenos=True,
            full=True,
            metrics=metrics,
        ),
    )
    reports_dir = Path(__file__).parents[1] / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = filename.replace("\\", ".").replace("/", ".")
    output = reports_dir / f"annotated_{filename}.html"
    logger.info(f"Saving {filename} annotated source code to {output}.")
    with output.open("w") as html:
        html.write(result)


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
        logger.error(
            f"Format must be HTML or CONSOLE, not {format}."
        )
        exit(1)

    annotate_revision(format=format, revision_index=revision)


if __name__ == "__main__":
    run()
