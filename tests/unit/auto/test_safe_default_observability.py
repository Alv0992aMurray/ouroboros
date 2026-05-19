"""Observability tests for safe-default finalization structured-log events.

Verifies that the structured-log events added by PR-A (instrumentation) are
emitted at the correct decision points inside ``AutoInterviewDriver.run`` and
``_unsafe_context_reason``.  Zero behaviour change is asserted by checking
that existing result semantics (status, blocker strings) are unchanged.
"""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from ouroboros.auto.interview_driver import (
    AutoInterviewDriver,
    FunctionInterviewBackend,
    InterviewTurn,
)
from ouroboros.auto.ledger import LedgerEntry, LedgerSource, LedgerStatus, SeedDraftLedger
from ouroboros.auto.safe_defaults import _unsafe_context_reason
from ouroboros.auto.state import AutoPipelineState, AutoStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ledger_with_goal_only(goal: str = "Build a local CLI") -> SeedDraftLedger:
    """Ledger with only the goal filled — all other required sections are open gaps."""
    return SeedDraftLedger.from_goal(goal)


def _ledger_all_filled_except(
    goal: str = "Build a local CLI", *, skip: str | None = None
) -> SeedDraftLedger:
    """Ledger with all required sections filled except *skip* (if given)."""
    ledger = SeedDraftLedger.from_goal(goal)
    for section, value in {
        "actors": "Single local CLI user",
        "inputs": "Command arguments",
        "outputs": "Stable stdout and files",
        "constraints": "Use existing project patterns",
        "non_goals": "No cloud sync",
        "acceptance_criteria": "Command prints stable output",
        "verification_plan": "Run command-level tests",
        "failure_modes": "Invalid input exits non-zero",
        "runtime_context": "Existing repository runtime",
    }.items():
        if section == skip:
            continue
        source = (
            LedgerSource.NON_GOAL if section == "non_goals" else LedgerSource.CONSERVATIVE_DEFAULT
        )
        ledger.add_entry(
            section,
            LedgerEntry(
                key=f"{section}.test",
                value=value,
                source=source,
                confidence=0.85,
                status=LedgerStatus.DEFAULTED,
            ),
        )
    return ledger


# ---------------------------------------------------------------------------
# Test 1: no_gaps_to_default + mutual_agreement_deadlock_at_max_rounds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_safe_default_logs_no_gaps_to_default(tmp_path) -> None:
    """Ledger already seed-ready but backend keeps asking → mutual-agreement deadlock path.

    The driver enters the safe-default fallback block after max_rounds with
    backend_done=False and ledger_done=True.  ``finalize_safe_defaultable_gaps``
    returns an empty defaulted_sections (no gaps to fill), so the driver emits
    ``no_gaps_to_default``.  Because ledger_done=True at the final blocker path
    the driver also emits ``mutual_agreement_deadlock_at_max_rounds``.
    """
    # Ledger is fully filled — is_seed_ready() returns True from round 0.
    ledger = _ledger_all_filled_except()
    assert ledger.is_seed_ready()

    async def start(goal: str, cwd: str) -> InterviewTurn:  # noqa: ARG001
        return InterviewTurn("What else should we know?", "interview_deadlock")

    async def answer(
        session_id: str, text: str, *, last_question: str | None = None
    ) -> InterviewTurn:  # noqa: ARG001
        # Backend never signals completion — it keeps asking.
        return InterviewTurn("What else should we know?", session_id, seed_ready=False)

    state = AutoPipelineState(goal="Build a local CLI", cwd=str(tmp_path))
    driver = AutoInterviewDriver(
        FunctionInterviewBackend(start, answer),
        store=AutoStore(tmp_path),
        max_rounds=1,
        timeout_seconds=1,
    )

    with capture_logs() as captured:
        result = await driver.run(state, ledger)

    events = [e["event"] for e in captured]
    assert "auto.interview.safe_default.entered" in events
    assert "auto.interview.safe_default.no_gaps_to_default" in events
    assert "auto.interview.mutual_agreement_deadlock_at_max_rounds" in events

    # Behaviour unchanged: blocked because backend never agreed.
    assert result.status == "blocked"
    assert "without closure" in (result.blocker or "")


# ---------------------------------------------------------------------------
# Test 2: safe_default.closed path with defaulted_sections field
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_safe_default_logs_closed_path(tmp_path) -> None:
    """Benign goal with no pre-filled ledger; backend keeps asking at max_rounds=1.

    After max_rounds the driver calls ``finalize_safe_defaultable_gaps``, which
    fills all open gaps including ``runtime_context``.  The synthesis push succeeds.
    The driver emits ``safe_default.entered`` and ``safe_default.closed`` (with
    ``defaulted_sections`` including ``runtime_context``), and the result status is
    ``seed_ready``.
    """
    ledger = SeedDraftLedger.from_goal("Build a tiny local CLI")
    assert not ledger.is_seed_ready()
    assert "runtime_context" in ledger.open_gaps()

    async def start(goal: str, cwd: str) -> InterviewTurn:  # noqa: ARG001
        return InterviewTurn("What else should we know?", "interview_closable")

    async def answer(
        session_id: str, text: str, *, last_question: str | None = None
    ) -> InterviewTurn:  # noqa: ARG001
        if "[safe-default-synthesis]" in text:
            return InterviewTurn("done", session_id, seed_ready=True, completed=True)
        return InterviewTurn("What else should we know?", session_id, seed_ready=False)

    state = AutoPipelineState(goal="Build a tiny local CLI", cwd=str(tmp_path))
    driver = AutoInterviewDriver(
        FunctionInterviewBackend(start, answer),
        store=AutoStore(tmp_path),
        max_rounds=1,
        timeout_seconds=1,
    )

    with capture_logs() as captured:
        result = await driver.run(state, ledger)

    events = [e["event"] for e in captured]
    assert "auto.interview.safe_default.entered" in events
    assert "auto.interview.safe_default.closed" in events

    # Verify the defaulted_sections field on the closed event includes runtime_context.
    closed_events = [e for e in captured if e["event"] == "auto.interview.safe_default.closed"]
    assert len(closed_events) == 1
    defaulted = closed_events[0]["defaulted_sections"]
    assert "runtime_context" in defaulted

    # Behaviour unchanged: seed ready after safe-default closure.
    assert result.status == "seed_ready"


# ---------------------------------------------------------------------------
# Test 3: unsafe_context_match logs pattern_name
# ---------------------------------------------------------------------------


def test_unsafe_context_match_logs_pattern_name() -> None:
    """Goal containing 'deploy to production' triggers the unsafe-context gate.

    ``_unsafe_context_reason`` must emit ``auto.safe_default.unsafe_context_match``
    with ``pattern_name == 'ambiguous external side effect'``.
    """
    ledger = SeedDraftLedger.from_goal("deploy to production")

    with capture_logs() as captured:
        reason = _unsafe_context_reason(
            ledger,
            goal="deploy to production",
            pending_question=None,
        )

    assert reason is not None

    match_events = [
        e for e in captured if e["event"] == "auto.safe_default.unsafe_context_match"
    ]
    assert len(match_events) >= 1
    assert match_events[0]["pattern_name"] == "ambiguous external side effect"
    assert "matched_token" in match_events[0]
    assert "matched_text_prefix" in match_events[0]
