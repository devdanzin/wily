"""
Raw statistics operator.

Includes insights like lines-of-code, number of comments. Does not measure complexity.
"""
from typing import Union

import radon.cli.harvest as harvesters
from radon.cli import Config
from radon.raw import Module
from radon.raw_visitor import RawClassMetrics, RawFunctionMetrics

from wily import logger
from wily.lang import _
from wily.operators import BaseOperator, Metric, MetricType


class RawMetricsOperator(BaseOperator):
    """Raw Metrics Operator."""

    name = "raw"
    defaults = {
        "exclude": None,
        "ignore": None,
        "summary": False,
        "include_ipynb": True,
        "ipynb_cells": True,
        "class_names": True,
    }
    metrics = (
        Metric("loc", _("Lines of Code"), int, MetricType.Informational, sum),
        Metric("lloc", _("L Lines of Code"), int, MetricType.AimLow, sum),
        Metric("sloc", _("S Lines of Code"), int, MetricType.AimLow, sum),
        Metric("comments", _("Multi-line comments"), int, MetricType.AimHigh, sum),
        Metric("multi", _("Multi lines"), int, MetricType.Informational, sum),
        Metric("blank", _("blank lines"), int, MetricType.Informational, sum),
        Metric(
            "single_comments",
            _("Single comment lines"),
            int,
            MetricType.Informational,
            sum,
        ),
    )
    default_metric_index = 0  # LOC

    def __init__(self, config, targets):
        """
        Instantiate a new raw operator.

        :param config: The wily configuration.
        :type  config: :class:`WilyConfig`
        """
        # TODO: Use config from wily.cfg for harvester
        logger.debug(f"Using {targets} with {self.defaults} for Raw metrics")
        self.harvester = harvesters.RawHarvester(
            targets, config=Config(**self.defaults)
        )

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
        logger.debug("Running raw harvester")
        results = {}
        for filename, details in dict(self.harvester.results).items():
            results[filename] = {"detailed": {}, "total": {}}
            for name, instance in details:
                if isinstance(instance, (Module, RawClassMetrics, RawFunctionMetrics)):
                    report_as_dict = self._report_to_dict(instance)
                    if name == "__ModuleMetrics__":
                        results[filename]["total"] = report_as_dict
                    else:
                        results[filename]["detailed"][name] = report_as_dict
                else:
                    if isinstance(instance, str) and instance == "error":
                        logger.debug(
                            f"Failed to run Raw harvester on {filename} : {details['error']}"
                        )
                        continue
        return results

    def _report_to_dict(
        self, report: Union[Module, RawFunctionMetrics, RawClassMetrics]
    ) -> dict:
        raw_metrics = {
            "loc": report.loc,
            "lloc": report.lloc,
            "sloc": report.sloc,
            "comments": report.comments,
            "multi": report.multi,
            "blank": report.blank,
            "single_comments": report.single_comments,
        }
        if hasattr(report, "lineno"):
            raw_metrics.update(
                {
                    "is_class": hasattr(report, "methods"),
                    "lineno": report.lineno,
                    "endline": report.endline,
                }
            )
        return raw_metrics
