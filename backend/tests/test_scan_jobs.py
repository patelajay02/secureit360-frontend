# backend/tests/test_scan_jobs.py
# Prove the repaired scheduler path:
#   * routes through the REAL run_full_scan (not the removed scan_orchestrator),
#   * calls it with the correct arguments and records completion,
#   * prevents duplicate jobs for the same tenant/target/cycle,
#   * records timeouts,
#   * surfaces real DB errors when claiming a job.

import inspect
import pytest

from services import scan_jobs


class FakeResp:
    def __init__(self, data=None, count=None):
        self.data = data if data is not None else []
        self.count = count


class FakeChain:
    """Chainable no-op query that returns empty data on execute()."""
    def __init__(self, resp=None):
        self._resp = resp or FakeResp([])

    def select(self, *a, **k): return self
    def insert(self, *a, **k): return self
    def update(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def in_(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self): return self._resp


class FakeSupabase:
    def table(self, name):
        return FakeChain()


def _patch_enrichment(monkeypatch):
    import services.threat_intel_scan as tis
    import services.score_calculator as sc

    async def _anoop(*a, **k):
        return None

    monkeypatch.setattr(tis, "run_threat_intel_scan", _anoop)
    monkeypatch.setattr(sc, "calculate_director_liability_score", lambda *a, **k: None)


# ── The critical regression test: the real scan entry point is wired up ──────
def test_scheduler_has_no_broken_orchestrator_import():
    import services.scheduler as sched
    src = inspect.getsource(sched)
    assert "scan_orchestrator" not in src, "scheduler must not import the removed module"


def test_scan_jobs_uses_real_full_scan():
    from services.full_scan import run_full_scan as real
    assert scan_jobs.run_full_scan is real


@pytest.mark.asyncio
async def test_run_daily_scan_calls_real_full_scan_with_correct_args(monkeypatch):
    calls = {}

    async def fake_full_scan(tenant_id, domain_id, domain, user_id):
        calls["args"] = (tenant_id, domain_id, domain, user_id)
        return {"status": "complete", "scan_id": "scan-1"}

    monkeypatch.setattr(scan_jobs, "run_full_scan", fake_full_scan)
    monkeypatch.setattr(scan_jobs, "validate_public_hostname", lambda d: d)
    monkeypatch.setattr(scan_jobs, "_pick_verified_target", lambda sb, tid: ("dom-1", "example.com"))
    monkeypatch.setattr(scan_jobs, "claim_scan_job", lambda *a, **k: {"id": "job-1"})
    marks = []
    monkeypatch.setattr(scan_jobs, "mark_job", lambda job_id, status, **k: marks.append(status))
    _patch_enrichment(monkeypatch)

    outcome = await scan_jobs.run_daily_scan_for_tenant(
        {"id": "t-1", "name": "Acme"}, FakeSupabase()
    )

    assert outcome == "completed"
    assert calls["args"] == ("t-1", "dom-1", "example.com", None)
    assert "running" in marks and "completed" in marks


@pytest.mark.asyncio
async def test_duplicate_cycle_is_skipped(monkeypatch):
    monkeypatch.setattr(scan_jobs, "_pick_verified_target", lambda sb, tid: ("dom-1", "example.com"))
    monkeypatch.setattr(scan_jobs, "claim_scan_job", lambda *a, **k: None)  # already claimed

    called = {"full": False}

    async def fake_full_scan(*a, **k):
        called["full"] = True
        return {}

    monkeypatch.setattr(scan_jobs, "run_full_scan", fake_full_scan)

    outcome = await scan_jobs.run_daily_scan_for_tenant({"id": "t-1"}, FakeSupabase())
    assert outcome == "skipped_duplicate"
    assert called["full"] is False, "no scan should run when the cycle is a duplicate"


@pytest.mark.asyncio
async def test_no_verified_target_is_skipped(monkeypatch):
    monkeypatch.setattr(scan_jobs, "_pick_verified_target", lambda sb, tid: None)
    outcome = await scan_jobs.run_daily_scan_for_tenant({"id": "t-1"}, FakeSupabase())
    assert outcome == "skipped_no_target"


@pytest.mark.asyncio
async def test_scan_timeout_marks_timed_out(monkeypatch):
    import asyncio
    monkeypatch.setattr(scan_jobs, "_pick_verified_target", lambda sb, tid: ("dom-1", "example.com"))
    monkeypatch.setattr(scan_jobs, "validate_public_hostname", lambda d: d)
    monkeypatch.setattr(scan_jobs, "claim_scan_job", lambda *a, **k: {"id": "job-1"})
    monkeypatch.setattr(scan_jobs, "DAILY_SCAN_TIMEOUT_SECONDS", 0.05)
    marks = []
    monkeypatch.setattr(scan_jobs, "mark_job", lambda job_id, status, **k: marks.append(status))

    async def slow(*a, **k):
        await asyncio.sleep(1)
        return {}

    monkeypatch.setattr(scan_jobs, "run_full_scan", slow)

    outcome = await scan_jobs.run_daily_scan_for_tenant({"id": "t-1"}, FakeSupabase())
    assert outcome == "timed_out"
    assert "timed_out" in marks


# ── Job-lock claim semantics ─────────────────────────────────────────────────
def test_claim_scan_job_returns_none_on_existing(monkeypatch):
    class Chain:
        def insert(self, *a, **k): raise Exception("duplicate key value violates unique constraint")
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def execute(self): return FakeResp([{"id": "existing", "status": "completed"}])

    class SB:
        def table(self, n): return Chain()

    monkeypatch.setattr(scan_jobs, "supabase_admin", SB())
    result = scan_jobs.claim_scan_job("t", "d", "daily_full", scan_jobs._today_nz())
    assert result is None


def test_claim_scan_job_raises_on_real_error(monkeypatch):
    class Chain:
        def insert(self, *a, **k): raise Exception("connection refused")
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def execute(self): return FakeResp([])  # no existing row

    class SB:
        def table(self, n): return Chain()

    monkeypatch.setattr(scan_jobs, "supabase_admin", SB())
    with pytest.raises(Exception):
        scan_jobs.claim_scan_job("t", "d", "daily_full", scan_jobs._today_nz())
