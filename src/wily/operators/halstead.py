"""
Halstead operator.

Measures all of the halstead metrics (volume, vocab, difficulty)
"""
import ast
import collections

import radon.cli.harvest as harvesters
from radon.cli import Config
from radon.metrics import Halstead, HalsteadReport, halstead_visitor_report
from radon.visitors import HalsteadVisitor

from wily import logger
from wily.lang import _
from wily.operators import BaseOperator, Metric, MetricType

NumberedHalsteadReport = collections.namedtuple(
    "NumberedHalsteadReport",
    HalsteadReport._fields + ("lineno", "endline"),
)


class NumberedHalsteadVisitor(HalsteadVisitor):
    def __init__(self, context=None, lineno=None, endline=None):
        super().__init__(context)
        self.lineno = lineno
        self.endline = endline

    def visit_FunctionDef(self, node):
        super().visit_FunctionDef(node)
        self.function_visitors[-1].lineno = node.lineno
        self.function_visitors[-1].endline = node.end_lineno


def number_report(visitor):
    return NumberedHalsteadReport(
        *(halstead_visitor_report(visitor) + (visitor.lineno, visitor.endline))
    )


class NumberedHCHarvester(harvesters.HCHarvester):
    def gobble(self, fobj):
        """Analyze the content of the file object."""
        code = fobj.read()
        visitor = NumberedHalsteadVisitor.from_ast(ast.parse(code))
        total = number_report(visitor)
        functions = [(v.context, number_report(v)) for v in visitor.function_visitors]
        return Halstead(total, functions)


class HalsteadOperator(BaseOperator):
    """Halstead Operator."""

    name = "halstead"
    defaults = {
        "exclude": None,
        "ignore": None,
        "min": "A",
        "max": "C",
        "multi": True,
        "show": False,
        "sort": False,
        "by_function": True,
        "include_ipynb": True,
        "ipynb_cells": True,
    }

    metrics = (
        Metric("h1", _("Unique Operands"), int, MetricType.AimLow, sum),
        Metric("h2", _("Unique Operators"), int, MetricType.AimLow, sum),
        Metric("N1", _("Number of Operands"), int, MetricType.AimLow, sum),
        Metric("N2", _("Number of Operators"), int, MetricType.AimLow, sum),
        Metric(
            "vocabulary", _("Unique vocabulary (h1 + h2)"), int, MetricType.AimLow, sum
        ),
        Metric("length", _("Length of application"), int, MetricType.AimLow, sum),
        Metric("volume", _("Code volume"), float, MetricType.AimLow, sum),
        Metric("difficulty", _("Difficulty"), float, MetricType.AimLow, sum),
        Metric("effort", _("Effort"), float, MetricType.AimLow, sum),
    )

    default_metric_index = 0  # MI

    def __init__(self, config, targets):
        """
        Instantiate a new HC operator.

        :param config: The wily configuration.
        :type  config: :class:`WilyConfig`
        """
        # TODO : Import config from wily.cfg
        logger.debug(f"Using {targets} with {self.defaults} for HC metrics")

        self.harvester = NumberedHCHarvester(targets, config=Config(**self.defaults))

    def run(self, module, options):
        """
        Run the operator.

        :param module: The target module path.
        :type  module: ``str``

        :param options: Any runtime options.
        :type  options: ``dict``

        :return: The operator results.
        :rtype: ``dict``
        """
        logger.debug("Running halstead harvester")
        results = {}
        for filename, details in dict(self.harvester.results).items():
            results[filename] = {"detailed": {}, "total": {}}
            for instance in details:
                if isinstance(instance, list):
                    for item in instance:
                        function, report = item
                        results[filename]["detailed"][function] = self._report_to_dict(
                            report
                        )
                else:
                    if isinstance(instance, str) and instance == "error":
                        logger.debug(
                            f"Failed to run Halstead harvester on {filename} : {details['error']}"
                        )
                        continue
                    results[filename]["total"] = self._report_to_dict(instance)
        return results

    def _report_to_dict(self, report):
        return {
            "h1": report.h1,
            "h2": report.h2,
            "N1": report.N1,
            "N2": report.N2,
            "vocabulary": report.vocabulary,
            "volume": report.volume,
            "length": report.length,
            "effort": report.effort,
            "difficulty": report.difficulty,
            "lineno": report.lineno,
            "endline": report.endline,
        }
