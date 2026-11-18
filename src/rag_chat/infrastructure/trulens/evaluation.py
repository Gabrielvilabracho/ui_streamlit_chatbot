"""Explicit, offline-only TruLens batch evaluation configuration and execution."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from trulens.core.run import RunConfig, RunStatus

from rag_chat.domain.errors import ConfigurationError


class ServerMetric(StrEnum):
    GROUNDEDNESS = "groundedness"
    CONTEXT_RELEVANCE = "context_relevance"
    ANSWER_RELEVANCE = "answer_relevance"
    COHERENCE = "coherence"
    CORRECTNESS = "correctness"


DEFAULT_SERVER_METRICS = (
    ServerMetric.GROUNDEDNESS,
    ServerMetric.CONTEXT_RELEVANCE,
    ServerMetric.ANSWER_RELEVANCE,
    ServerMetric.COHERENCE,
)


@dataclass(frozen=True, slots=True)
class BatchEvaluationSettings:
    dataset_name: str
    run_name: str
    judge_model: str
    input_column: str = "QUESTION"
    ground_truth_column: str | None = None
    metrics: tuple[ServerMetric, ...] = DEFAULT_SERVER_METRICS
    invocation_max_workers: int | None = None
    metric_max_workers: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("TRULENS_EVAL_DATASET", self.dataset_name),
            ("TRULENS_EVAL_RUN", self.run_name),
            ("TRULENS_EVAL_JUDGE_MODEL", self.judge_model),
            ("TRULENS_EVAL_INPUT_COLUMN", self.input_column),
        ):
            if not value.strip():
                raise ConfigurationError(f"{name} is required for batch evaluation.")
        if not self.metrics:
            raise ConfigurationError(
                "TRULENS_EVAL_METRICS must select at least one metric."
            )
        if ServerMetric.CORRECTNESS in self.metrics and not self.ground_truth_column:
            raise ConfigurationError(
                "TRULENS_EVAL_GROUND_TRUTH_COLUMN is required when correctness is selected."
            )

    @classmethod
    def from_sources(
        cls,
        *,
        secrets: Mapping[str, Any],
        environ: Mapping[str, str] | None = None,
    ) -> BatchEvaluationSettings:
        environment = environ if environ is not None else os.environ
        nested = secrets.get("trulens_evaluation", {})
        nested_secrets = nested if isinstance(nested, Mapping) else {}

        def value(name: str, *, default: str | None = None) -> str | None:
            short_name = name.removeprefix("TRULENS_EVAL_").lower()
            raw = nested_secrets.get(short_name, secrets.get(name, environment.get(name, default)))
            if raw is None:
                return None
            normalized = str(raw).strip()
            return normalized or None

        dataset_name = _required(value("TRULENS_EVAL_DATASET"), "TRULENS_EVAL_DATASET")
        run_name = _required(value("TRULENS_EVAL_RUN"), "TRULENS_EVAL_RUN")
        judge_model = _required(
            value("TRULENS_EVAL_JUDGE_MODEL"),
            "TRULENS_EVAL_JUDGE_MODEL",
        )
        ground_truth_column = value("TRULENS_EVAL_GROUND_TRUTH_COLUMN")
        metrics = _parse_metrics(value("TRULENS_EVAL_METRICS"))
        return cls(
            dataset_name=dataset_name,
            run_name=run_name,
            judge_model=judge_model,
            input_column=value("TRULENS_EVAL_INPUT_COLUMN", default="QUESTION")
            or "QUESTION",
            ground_truth_column=ground_truth_column,
            metrics=metrics,
            invocation_max_workers=_optional_positive_integer(
                value("TRULENS_EVAL_INVOCATION_WORKERS"),
                "TRULENS_EVAL_INVOCATION_WORKERS",
            ),
            metric_max_workers=_optional_positive_integer(
                value("TRULENS_EVAL_METRIC_WORKERS"),
                "TRULENS_EVAL_METRIC_WORKERS",
            ),
        )


class BatchRun(Protocol):
    def start(self) -> None: ...

    def get_status(self) -> RunStatus: ...

    def compute_metrics(self, metrics: list[str]) -> str: ...


class BatchApp(Protocol):
    def add_run(self, *, run_config: RunConfig) -> BatchRun | None: ...


def build_run_config(settings: BatchEvaluationSettings) -> RunConfig:
    """Build a table-backed app-invocation run without starting remote work."""

    dataset_spec = {
        "RETRIEVAL.QUERY_TEXT": settings.input_column,
        "RECORD_ROOT.INPUT": settings.input_column,
    }
    if settings.ground_truth_column:
        dataset_spec["RECORD_ROOT.GROUND_TRUTH_OUTPUT"] = (
            settings.ground_truth_column
        )
    return RunConfig(
        run_name=settings.run_name,
        dataset_name=settings.dataset_name,
        source_type="TABLE",
        dataset_spec=dataset_spec,
        description="Offline Sof~IA quality evaluation over recorded RAG traces.",
        label="sofia-batch-evaluation",
        llm_judge_name=settings.judge_model,
        invocation_max_workers=settings.invocation_max_workers,
        metric_max_workers=settings.metric_max_workers,
    )


def create_batch_run(
    *,
    tru_app: BatchApp,
    settings: BatchEvaluationSettings,
) -> BatchRun:
    """Create a named TruLens run; execution remains a separate explicit action."""

    run = tru_app.add_run(run_config=build_run_config(settings))
    if run is None:
        raise RuntimeError("TruLens did not return the requested batch run.")
    return run


def execute_batch_run(
    *,
    run: BatchRun,
    metrics: Sequence[ServerMetric],
    poll_interval_seconds: float = 5.0,
    timeout_seconds: float = 1_800.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Explicitly invoke a run, wait for ingestion, then start paid metrics."""

    if poll_interval_seconds <= 0 or timeout_seconds <= 0:
        raise ValueError("Polling interval and timeout must be positive.")

    started_at = clock()
    run.start()
    while True:
        status = run.get_status()
        if status in {
            RunStatus.INVOCATION_COMPLETED,
            RunStatus.INVOCATION_PARTIALLY_COMPLETED,
        }:
            break
        if status in {
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.UNKNOWN,
            RunStatus.COMPLETED,
            RunStatus.PARTIALLY_COMPLETED,
            RunStatus.COMPUTATION_IN_PROGRESS,
        }:
            raise RuntimeError(f"TruLens batch invocation stopped with {status.value}.")
        if clock() - started_at >= timeout_seconds:
            raise TimeoutError("TruLens batch invocation did not finish before the timeout.")
        sleep(poll_interval_seconds)

    return run.compute_metrics([metric.value for metric in metrics])


def _parse_metrics(value: str | None) -> tuple[ServerMetric, ...]:
    if value is None:
        return DEFAULT_SERVER_METRICS

    metrics: list[ServerMetric] = []
    for raw_metric in value.split(","):
        normalized = raw_metric.strip().lower()
        if not normalized:
            continue
        try:
            metric = ServerMetric(normalized)
        except ValueError as error:
            raise ConfigurationError(
                f"TRULENS_EVAL_METRICS contains unsupported metric: {normalized}."
            ) from error
        if metric not in metrics:
            metrics.append(metric)
    if not metrics:
        raise ConfigurationError("TRULENS_EVAL_METRICS must select at least one metric.")
    return tuple(metrics)


def _optional_positive_integer(value: str | None, name: str) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a positive integer.") from error
    if parsed <= 0:
        raise ConfigurationError(f"{name} must be a positive integer.")
    return parsed


def _required(value: str | None, name: str) -> str:
    if value is None:
        raise ConfigurationError(f"{name} is required for batch evaluation.")
    return value
