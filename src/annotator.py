"""Annotate source code with metrics."""

import json
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter, TerminalFormatter
from pygments.lexers import PythonLexer

from wily.config import DEFAULT_CONFIG_PATH
from wily.config import load as load_config
from wily.state import IndexedRevision, State


class AnnotatedHTMLFormatter(HtmlFormatter):
    """Annotate and color source code with metric values as HTML."""

    def __init__(self, metrics=None, **options):
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
            if i in self.metrics:
                if self.metrics[i][1] == "-":  # Just use function/method values for now
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
        metric_values = " ".join(self.metrics.get(self._lineno - 1, ("-", "-")))
        outfile.write(
            f"%s%04d: {metric_values} |"
            % (self._lineno != 1 and "\n" or "", self._lineno)
        )


def last_line(details):
    """Get the last line from a series of detailed metric entries."""
    lineends = []
    for _name, detail in details.items():
        lineends.append(detail["endline"])
    return max(lineends)


def map_lines(details):
    """Map metric values to lines, for functions/methods and classes."""
    last = last_line(details)
    lines = {i: ["-", "-"] for i in range(last + 1)}
    for _name, detail in details.items():
        if "is_method" in detail:
            for line in range(detail["lineno"] - 1, detail["endline"]):
                lines[line] = lines[line][0], str(detail["complexity"])
        else:
            for line in range(detail["lineno"] - 1, detail["endline"]):
                lines[line] = str(detail["complexity"]), lines[line][1]
    return lines


def annotate_revision(format="HTML"):
    """Generate annotated files from detailed metric data in a revision."""
    config = load_config(DEFAULT_CONFIG_PATH)
    state = State(config)
    target_revision: IndexedRevision = state.index[state.default_archiver].last_revision
    rev_data = Path(config.cache_path) / "git" / f"{target_revision.revision.key}.json"
    as_dict = json.loads(rev_data.read_text())
    py_files = [
        key
        for key in as_dict["operator_data"]["cyclomatic"].keys()
        if key.endswith(".py")
    ]
    for filename in py_files:
        details = as_dict["operator_data"]["cyclomatic"][filename]["detailed"]
        path = Path(filename)
        code = path.read_text()
        metrics = map_lines(details)
        if format.lower() == "html":
            generate_annotated_html(code, filename, metrics, target_revision)
        elif format.lower() == "console":
            print_annotated_source(code, metrics)


def print_annotated_source(code, metrics):
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


def generate_annotated_html(code, filename, metrics, target_revision):
    """Generate an annotated HTML file from source code and metric data."""
    result = highlight(
        code,
        PythonLexer(),
        AnnotatedHTMLFormatter(
            title=f"CC for {filename} at {target_revision.revision.key[:7]}",
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
    with output.open("w") as html:
        html.write(result)


if __name__ == "__main__":
    annotate_revision("console")
