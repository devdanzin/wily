"""Annotate source code with metrics."""
from __future__ import annotations

import json
import logging
import shutil
from collections import defaultdict
from pathlib import Path
from string import Template
from sys import exit
from typing import Any, Optional

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

# Maximum values for each metric, i.e. what will result in red background
MAX_DICT = {
    "cc_function": 50,
    "h1": 40,
    "h2": 40,
    "N1": 40,
    "N2": 40,
    "vocabulary": 80,
    "length": 80,
    "volume": 500,
    "effort": 2000,
    "difficulty": 40,
}


def get_metric_color(val: float, maximum: int = 50, name: Optional[str] = None) -> str:
    """
    Calculate RGB values for a scale from green to red through yellow.

    :param val: The value to convert to RGB color.
    :param maximum: The maximum expected value, corresponding to one less than red.
    :param name: A name to get a maximum value from MAX_DICT.
    :return: A string of the form `"rgba(X, Y, 0, 0.75)"`.
    """
    if name is not None:
        maximum = MAX_DICT[name]
    factor = 2 / maximum
    red = max(0, min(255, round(factor * 255 * (val - 1))))
    green = max(0, min(255, round(factor * 255 * (maximum - val + 1))))
    blue = 0
    return f"rgba{(red, green, blue, 0.75)}"


class AnnotatedHTMLFormatter(HtmlFormatter):
    """Annotate and color source code with metric values as HTML."""

    halstead_names = (
        "h1",
        "h2",
        "N1",
        "N2",
        "vocabulary",
        "length",
        "volume",
        "effort",
        "difficulty",
    )
    metric_names = halstead_names + ("cc_function",)

    def __init__(
        self, metrics: list[dict[int, tuple[str, str]]], **options: Any
    ) -> None:
        """Set up the formatter instance with metrics."""
        super().__init__(**options)
        self.cyclomatic = metrics[0]
        self.halstead = metrics[1]

        halstead_spans: list[str] = []
        # These should match the column widths of Halstead metrics in map_halstead_lines
        empty_halstead_vals = ("---",) * 6 + ("-------",) * 3
        for name, val in zip(self.halstead_names, empty_halstead_vals):
            halstead_spans.append(
                f'<span class="halstead_span {name}_val {name}none">{val} </span>'
            )
        self.empty_halstead_spans = "".join(halstead_spans)

        # These should match the column widths of CC metrics in map_cyclomatic_lines
        empty_cyclomatic_vals = ("--", "--")
        self.empty_cyclomatic_span = (
            '<span class="cyclomatic_span cc_function_val cc_functionnone" style="background-color: #ffffff;">'
            f'{" ".join(empty_cyclomatic_vals)} </span>'
        )

        # This will be used to create the CSS entries for all classes
        self.metric_styles: dict[str, str] = {
            f"{name}none": "#ffffff" for name in self.metric_names
        }

    def wrap(self, source) -> None:
        """Wrap the ``source`` in custom generators."""
        output = source
        output = self.annotate_lines(output)
        if self.wrapcode:
            output = self._wrap_code(output)
        output = self._wrap_pre(output)
        return output

    def annotate_lines(self, tokensource):
        """
        Add metric annotations from self.cyclomatic and self.halstead.

        A div is created for each code line, containing spans for each metric
        value. This div and the spans have associated CSS classes that allow
        changing the background color of the code to match selected metric
        values and also hiding unselected metrics.
        """
        for i, (_t, value) in enumerate(tokensource):
            if not self.cyclomatic:  # No metrics
                yield 1, value
                continue

            div_classes = [f"{name}none" for name in self.metric_names]
            if i in self.cyclomatic:  # Line has metric info available
                cyclomatic = self.get_cyclomatic_content(div_classes, i)
                halstead = self.get_halstead_content(div_classes, i)
                yield 1, (
                    f'<div class="{" ".join(div_classes)}">'
                    f"{cyclomatic}"
                    f"{halstead}| {value}</div>"
                )
            else:  # Line is after last known line, add empty metric spans
                yield 1, (
                    f'<div class="{" ".join(div_classes)}" style="background-color: #ffffff; width: 100%;">'
                    f"{self.empty_cyclomatic_span}"
                    f"{self.empty_halstead_spans}| {value}</div>"
                )

    def get_halstead_content(self, div_classes: list[str], i: int) -> str:
        """
        Build spans and add styles for Halstead metrics.

        :param div_classes: A list containing CSS class names.
        :param i: Index into self.halstead, corresponding to a source code line.
        :return: A string containing styled spans with Halstead metric values.
        """
        if i not in self.halstead or self.halstead[i][1][1] == "-":
            # Line is either not known or has empty metric value ("-").
            halstead = self.empty_halstead_spans
        else:
            spans = []
            for name, val in zip(self.halstead_names, self.halstead[i]):
                val_ = int(float(val))
                nameval = f"{name}{val_}"
                spans.append(
                    f'<span class="halstead_span {name}_val {nameval}">{val} </span>'
                )
                if nameval not in self.metric_styles:
                    h = get_metric_color(val_, name=name)
                    self.metric_styles[nameval] = h
                div_classes.append(f"{nameval}_code")
            halstead = "".join(spans)
        return halstead

    def get_cyclomatic_content(self, div_classes: list[str], i: int) -> str:
        """
        Build span and add styles for Cyclomatic Complexity.

        :param div_classes: A list containing CSS class names.
        :param i: Index into self.cyclomatic, corresponding to a source code line.
        :return: A string containing styled spans with Cyclomatic metric values.
        """
        if self.cyclomatic[i][0][1] == self.cyclomatic[i][1][1] == "-":
            cyclomatic = self.empty_cyclomatic_span  # No metric values
        elif self.cyclomatic[i][0][1] != "-" and self.cyclomatic[i][1][1] == "-":
            cyclomatic = (  # Only class metric values
                '<span class="cyclomatic_span cc_function_val">'
                f'{" ".join(self.cyclomatic[i])} </span>'
            )
        else:  # Function/method metric values, maybe class too
            val = int(self.cyclomatic[i][1])
            name = "cc_function"
            c = get_metric_color(val, name=name)
            cc_nameval = f"{name}{val}"
            if cc_nameval not in self.metric_styles:
                self.metric_styles[cc_nameval] = c
            div_classes.append(f"{cc_nameval}_code")
            cyclomatic = (
                f'<span class="cyclomatic_span cc_function_val {cc_nameval}">'
                f'{" ".join(self.cyclomatic[i])} </span>'
            )
        return cyclomatic

    def get_halstead_style_defs(self) -> str:
        """Get additional CSS rules from calculated styles seen."""
        result = []
        for name, value in self.metric_styles.items():
            result.append(f".{name} {{ background-color: {value};}}")
        return "\n" + "\n".join(result)


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
    """
    Get the last line from a series of detailed metric entries.

    :param details: A dict with detailed metric information, with line numbers.
    :return: The number of the last known line.
    """
    lineends = []
    for _name, detail in details.items():
        endline: int = detail.get("endline", 0)
        lineends.append(endline)
    return max(lineends or [0])


def map_cyclomatic_lines(details: dict) -> dict[int, tuple[str, str]]:
    """
    Map complexity metric values to lines, for functions/methods and classes.

    :param details: A dict with detailed metric information, with line numbers.
    :return: A dict mapping line numbers to Cyclomatic Complexity values.
    """
    last = last_line(details)
    lines = {i: ("--", "--") for i in range(last + 1)}
    for _name, detail in details.items():
        if "is_method" in detail:  # It's a function or method
            for line in range(detail["lineno"] - 1, detail["endline"]):
                lines[line] = (lines[line][0], f"{detail['complexity']:02d}")
        else:  # It's a class
            for line in range(detail["lineno"] - 1, detail["endline"]):
                lines[line] = (f"{detail['complexity']:02d}", lines[line][1])
    return lines


def map_halstead_lines(details: dict) -> dict[int, tuple[str, ...]]:
    """
    Map Halstead metric values to lines, for functions.

    :param details: A dict with detailed metric information, with line numbers.
    :return: A dict mapping line numbers to Halstead values.
    """
    last = last_line(details)
    lines = {i: ("---",) * 6 + ("-------",) * 3 for i in range(last + 1)}
    for _name, detail in details.items():
        if "lineno" not in detail or detail["lineno"] is None:
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


def bulk_annotate(output_dir: Optional[Path] = None) -> None:
    """
    Annotate all Python files found in the index's revisions.

    :param output_dir: A Path pointing to the directory to output HTML files.
    """
    config = load_config(DEFAULT_CONFIG_PATH)
    state = State(config)
    styles = {}
    if output_dir is None:
        output_dir = Path("reports")
    reports_dir = Path(__file__).parents[1] / output_dir
    reports_dir.mkdir(exist_ok=True)
    templates_dir = (Path(__file__).parent / "wily" / "templates").resolve()
    shutil.copyfile(templates_dir / "annotated.js", reports_dir / "annotated.js")
    css_output = reports_dir / "annotated.css"
    css_output.unlink(missing_ok=True)

    latest = get_latest_rev(
        config.cache_path, state.index[state.default_archiver].revision_keys
    )
    for filename, rev_key in latest.items():
        try:
            styles.update(
                annotate_revision(
                    format="HTML",
                    revision_index=rev_key,
                    path=filename,
                    css=False,
                    output_dir=output_dir,
                )
            )
        except FileNotFoundError:
            logger.error(
                f"Path {filename} not found in current state of git repository."
            )
    append_css(css_output, styles)


def get_latest_rev(cache_path: str, revision_keys: list[str]) -> dict[str, str]:
    """
    Get latest known revision for files.

    :param cache_path: The cache path from the config, used to find JSON files.
    :param revision_keys: A list of revision keys.
    :return: A dict mapping filenames to last known revision.
    """
    latest: dict[str, str] = {}
    for rev_key in revision_keys:
        rev_data = Path(cache_path) / "git" / f"{rev_key}.json"
        as_dict = json.loads(rev_data.read_text())
        cyclomatic = as_dict["operator_data"]["cyclomatic"]
        for filename, _data in cyclomatic.items():
            if filename.endswith(".py") and filename not in latest:
                latest[filename] = rev_key
    return latest


def append_css(css_output: Path, styles: dict[str, str]):
    """
    Append CSS from a style dict to a CSS file.

    :param css_output: Path to the output CSS file.
    :param styles: A dict of single CSS class names and background color values.
    """
    result = []
    for name, value in simplify_css(styles).items():
        result.append(f"{name} {{ background-color: {value};}}")
    with css_output.open("a") as css:
        css.write("\n\n" + "\n".join(result))


def simplify_css(styles: dict[str, str]) -> dict[str, str]:
    """
    Collapse rules that use the same color to a single line.

    :param styles: A dict of single CSS class names and background color values.
    :return: A dict of multiple CSS class names mapping to background color values.
    """
    colors_to_rules: defaultdict[str, list[str]] = defaultdict(list)
    for name, color in styles.items():
        colors_to_rules[color].append(name)
    return {f".{', .'.join(names)}": color for color, names in colors_to_rules.items()}


def annotate_revision(
    format: str = "HTML",
    revision_index: str = "",
    path: str = "",
    css: bool = False,
    output_dir: Optional[Path] = None,
) -> dict[str, str]:
    """
    Generate annotated files from detailed metric data in a revision.

    :param format: Either `HTML` or `CONSOLE`, determines output format.
    :param revision_index: A Git revision to annotate at.
    :param path: A single filename to annotate.
    :param css: Whether to write a CSS file containing styles.
    :param output_dir: A Path pointing to the directory to output HTML files.
    :return: A dict mapping CSS class names to color values.
    """
    config = load_config(DEFAULT_CONFIG_PATH)
    state = State(config)
    repo = Repo(config.path)

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
        target_revision: IndexedRevision
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
    if path:
        if path not in cyclomatic:
            logger.error(f"Data for file {path} not found on revision {rev_key}.")
            exit(1)
        else:
            py_files = [path]
    else:
        py_files = [key for key in cyclomatic if key.endswith(".py")]
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
    styles: dict[str, str] = {}
    for filename in py_files:
        diff = commit.diff(None, filename)
        outdated = False
        if diff and diff[0].change_type in ("M",):
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
        metrics = [
            map_cyclomatic_lines(cyclomatic[filename]["detailed"]),
            map_halstead_lines(halstead[filename]["detailed"]),
        ]
        if format.lower() == "html":
            style = generate_annotated_html(
                code, filename, metrics, target_revision.revision.key, output_dir
            )
            styles.update(style)
        elif format.lower() == "console":
            print_annotated_source(code, metrics[0])
    if format.lower() == "html":
        reports_dir = Path(__file__).parents[1] / output_dir
        templates_dir = (Path(__file__).parent / "wily" / "templates").resolve()
        js_file = reports_dir / "annotated.js"
        if not js_file.exists():
            shutil.copyfile(templates_dir / "annotated.js", js_file)
        if css:
            css_output = reports_dir / "annotated.css"
            append_css(css_output, styles)
    return styles


def print_annotated_source(code: str, metrics: dict[int, tuple[str, str]]) -> None:
    """
    Print source annotated with metric to terminal.

    :param code: The source code to highlight.
    :param metrics: Map of lines to CC metric values.
    """
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
    code: str,
    filename: str,
    metrics: list[dict[int, tuple[str, str]]],
    key: str,
    output_dir: Optional[Path] = None,
) -> dict[str, str]:
    """
    Generate an annotated HTML file from source code and metric data.

    :param code: The source code to highlight.
    :param filename: The filename to display in HTML and base HTML file name on.
    :param metrics: Two maps of lines to metric values (CC and Halstead).
    :param key: A Git revision key to display in title.
    :param output_dir: A Path pointing to the directory to output HTML files.
    :return: A map of CSS class names to background color values.
    """
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
    if output_dir is None:
        output_dir = Path("reports")
    reports_dir = Path(__file__).parents[1] / output_dir
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
    if not (reports_dir / "annotated.js").exists():
        shutil.copyfile(templates_dir / "annotated.js", reports_dir / "annotated.js")
    return formatter.metric_styles


@click.group(help="Annotate source files with metric values.")
def run() -> None:
    pass


@run.command()
@click.option(
    "-f",
    "--format",
    default="CONSOLE",
    help="Save HTML or print to CONSOLE.",
    type=click.STRING,
)
@click.option(
    "-r",
    "--revision",
    default="HEAD",
    help="Annotate with metric values from specific revision.",
    type=click.STRING,
)
@click.option(
    "-p",
    "--path",
    default="",
    help="Path to annotate.",
    type=click.Path(),
)
@click.option(
    "-c",
    "--css/--no-css",
    default=True,
    help="Write CSS file with styles to highlight code and metrics.",
)
@click.option(
    "-o",
    "--output",
    default="reports",
    help="Output directory to write files to.",
    type=click.Path(path_type=Path),
)
def annotate(format: str, revision: str, path: str, css: bool, output: Path) -> None:
    """Generate annotated source for a revision or single file."""
    if format.lower() not in ("html", "console"):
        logger.error(f"Format must be HTML or CONSOLE, not {format}.")
        exit(1)

    annotate_revision(
        format=format, revision_index=revision, path=path, css=css, output_dir=output
    )


@run.command("bulk-annotate")
@click.option(
    "-o",
    "--output",
    default="reports",
    help="Output directory to write files to.",
    type=click.Path(path_type=Path),
)
def bulk(output: Path):
    """Annotate all Python files from all known revisions."""
    bulk_annotate(output_dir=output)


if __name__ == "__main__":
    run()
