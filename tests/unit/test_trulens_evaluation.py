from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from trulens.core.run import RunConfig, RunStatus

from rag_chat.domain.errors import ConfigurationError
from rag_chat.infrastructure.trulens.evaluation import (
    BatchEvaluationSettings,
    ServerMetric,
    build_run_config,
    create_batch_run,
    execute_batch_run,
)


def test_evaluation_settings_default_to_server_side_quality_metrics() -> None:
    settings = BatchEvaluationSettings.from_sources(
        secrets={},
        environ={
            "TRULENS_EVAL_DATASET": "SOFIA_EVAL_QUESTIONS",
            "TRULENS_EVAL_RUN": "nightly-v1",
            "TRULENS_EVAL_JUDGE_MODEL": "llama3.3-70b",
        },
    )

    assert settings.metrics == (
        ServerMetric.GROUNDEDNESS,
        ServerMetric.CONTEXT_RELEVANCE,
        ServerMetric.ANSWER_RELEVANCE,
        ServerMetric.COHERENCE,
    )
    assert settings.ground_truth_column is None


def test_correctness_requires_an_explicit_ground_truth_column() -> None:
    with pytest.raises(ConfigurationError, match="GROUND_TRUTH_COLUMN"):
        BatchEvaluationSettings.from_sources(
            secrets={},
            environ={
                "TRULENS_EVAL_DATASET": "SOFIA_EVAL_QUESTIONS",
                "TRULENS_EVAL_RUN": "nightly-v1",
                "TRULENS_EVAL_JUDGE_MODEL": "llama3.3-70b",
                "TRULENS_EVAL_METRICS": "groundedness,correctness",
            },
        )


def test_direct_settings_reject_correctness_without_ground_truth() -> None:
    with pytest.raises(ConfigurationError, match="GROUND_TRUTH_COLUMN"):
        BatchEvaluationSettings(
            dataset_name="SOFIA_EVAL_QUESTIONS",
            run_name="release-v7",
            judge_model="llama3.3-70b",
            metrics=(ServerMetric.CORRECTNESS,),
        )


def test_evaluation_settings_reject_unknown_server_metrics() -> None:
    with pytest.raises(ConfigurationError, match="unsupported_metric"):
        BatchEvaluationSettings.from_sources(
            secrets={},
            environ={
                "TRULENS_EVAL_DATASET": "SOFIA_EVAL_QUESTIONS",
                "TRULENS_EVAL_RUN": "nightly-v1",
                "TRULENS_EVAL_JUDGE_MODEL": "llama3.3-70b",
                "TRULENS_EVAL_METRICS": "groundedness,unsupported_metric",
            },
        )


def test_explicit_empty_metric_selection_is_rejected() -> None:
    with pytest.raises(
        ConfigurationError,
        match="TRULENS_EVAL_METRICS must select at least one metric",
    ):
        BatchEvaluationSettings.from_sources(
            secrets={},
            environ={
                "TRULENS_EVAL_DATASET": "SOFIA_EVAL_QUESTIONS",
                "TRULENS_EVAL_RUN": "release-v7",
                "TRULENS_EVAL_JUDGE_MODEL": "llama3.3-70b",
                "TRULENS_EVAL_METRICS": "",
            },
        )


def test_direct_settings_reject_metrics_outside_allow_list() -> None:
    with pytest.raises(ConfigurationError, match="unsupported metric"):
        BatchEvaluationSettings(
            dataset_name="SOFIA_EVAL_QUESTIONS",
            run_name="release-v7",
            judge_model="llama3.3-70b",
            metrics=("unsupported_metric",),  # type: ignore[arg-type]
        )


def test_run_config_maps_named_table_input_and_optional_ground_truth() -> None:
    settings = BatchEvaluationSettings(
        dataset_name="SOFIA_EVAL_QUESTIONS",
        run_name="release-v7",
        judge_model="llama3.3-70b",
        input_column="QUESTION",
        ground_truth_column="EXPECTED_ANSWER",
        metrics=(ServerMetric.GROUNDEDNESS, ServerMetric.CORRECTNESS),
    )

    config = build_run_config(settings)

    assert config.dataset_name == "SOFIA_EVAL_QUESTIONS"
    assert config.run_name == "release-v7"
    assert config.source_type == "TABLE"
    assert config.dataset_spec == {
        "RETRIEVAL.QUERY_TEXT": "QUESTION",
        "RECORD_ROOT.INPUT": "QUESTION",
        "RECORD_ROOT.GROUND_TRUTH_OUTPUT": "EXPECTED_ANSWER",
    }
    assert config.llm_judge_name == "llama3.3-70b"


@dataclass
class FakeRun:
    statuses: list[RunStatus]
    calls: list[object] = field(default_factory=list)

    def start(self) -> None:
        self.calls.append("start")

    def get_status(self) -> RunStatus:
        self.calls.append("status")
        return self.statuses.pop(0)

    def compute_metrics(self, metrics: list[str]) -> str:
        self.calls.append(("metrics", metrics))
        return "started"


class FakeTruApp:
    def __init__(self, run: FakeRun) -> None:
        self.run = run
        self.config: RunConfig | None = None

    def add_run(self, *, run_config: RunConfig) -> FakeRun:
        self.config = run_config
        return self.run


def test_batch_run_waits_for_ingestion_before_server_metrics() -> None:
    settings = BatchEvaluationSettings(
        dataset_name="SOFIA_EVAL_QUESTIONS",
        run_name="release-v7",
        judge_model="llama3.3-70b",
    )
    run = FakeRun(
        statuses=[
            RunStatus.INVOCATION_IN_PROGRESS,
            RunStatus.INVOCATION_COMPLETED,
        ]
    )
    tru_app = FakeTruApp(run)
    sleeps: list[float] = []

    created_run = create_batch_run(tru_app=tru_app, settings=settings)
    result = execute_batch_run(
        run=created_run,
        metrics=settings.metrics,
        poll_interval_seconds=0.25,
        timeout_seconds=5,
        clock=iter((0.0, 0.1, 0.2)).__next__,
        sleep=sleeps.append,
    )

    assert result == "started"
    assert run.calls == [
        "start",
        "status",
        "status",
        (
            "metrics",
            [
                "groundedness",
                "context_relevance",
                "answer_relevance",
                "coherence",
            ],
        ),
    ]
    assert sleeps == [0.25]


def test_batch_run_failure_never_starts_paid_metrics() -> None:
    run = FakeRun(statuses=[RunStatus.FAILED])

    with pytest.raises(RuntimeError, match="FAILED"):
        execute_batch_run(
            run=run,
            metrics=(ServerMetric.GROUNDEDNESS,),
            clock=iter((0.0, 0.1)).__next__,
            sleep=lambda _: None,
        )

    assert not any(isinstance(call, tuple) for call in run.calls)


def test_partially_completed_invocation_can_score_completed_records() -> None:
    run = FakeRun(statuses=[RunStatus.INVOCATION_PARTIALLY_COMPLETED])

    execute_batch_run(
        run=run,
        metrics=(ServerMetric.GROUNDEDNESS,),
        clock=iter((0.0,)).__next__,
        sleep=lambda _: None,
    )

    assert run.calls[-1] == ("metrics", ["groundedness"])
