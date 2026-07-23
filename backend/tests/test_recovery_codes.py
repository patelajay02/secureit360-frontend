# backend/tests/test_recovery_codes.py
import services.recovery_codes as rc


class FakeTable:
    """In-memory fake of the mfa_recovery_codes table supporting the calls used."""
    def __init__(self, store):
        self.store = store
        self._op = None
        self._filters = {}
        self._pending = None

    def insert(self, rows):
        self._op = "insert"
        self._pending = rows
        return self

    def delete(self):
        self._op = "delete"
        return self

    def select(self, *a, **k):
        self._op = "select"
        return self

    def update(self, values):
        self._op = "update"
        self._pending = values
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def is_(self, col, val):
        # only used as .is_("used_at", "null")
        self._filters["__used_null"] = True
        return self

    def _match(self, row):
        for k, v in self._filters.items():
            if k.startswith("__"):
                continue
            if row.get(k) != v:
                return False
        if self._filters.get("__used_null") and row.get("used_at") is not None:
            return False
        return True

    def execute(self):
        if self._op == "insert":
            for r in self._pending:
                r.setdefault("id", f"id-{len(self.store)}")
                r.setdefault("used_at", None)
                self.store.append(dict(r))
            return type("R", (), {"data": self._pending})()
        if self._op == "delete":
            keep = [r for r in self.store if not self._match(r)]
            removed = len(self.store) - len(keep)
            self.store[:] = keep
            return type("R", (), {"data": [], "count": removed})()
        if self._op == "select":
            return type("R", (), {"data": [dict(r) for r in self.store if self._match(r)]})()
        if self._op == "update":
            for r in self.store:
                if self._match(r):
                    r.update(self._pending)
            return type("R", (), {"data": []})()
        return type("R", (), {"data": []})()


class FakeSB:
    def __init__(self):
        self.store = []
    def table(self, name):
        assert name == "mfa_recovery_codes"
        return FakeTable(self.store)


def test_generate_returns_ten_plaintext_codes(monkeypatch):
    sb = FakeSB()
    monkeypatch.setattr(rc, "supabase_admin", sb)
    codes = rc.generate_recovery_codes("u1")
    assert len(codes) == 10
    # stored rows are HASHED (salt:hash), never plaintext
    assert len(sb.store) == 10
    for row in sb.store:
        assert ":" in row["code_hash"]
        for c in codes:
            assert c not in row["code_hash"]           # plaintext never stored
            assert rc._normalize(c) not in row["code_hash"]


def test_verify_consumes_code_one_time(monkeypatch):
    sb = FakeSB()
    monkeypatch.setattr(rc, "supabase_admin", sb)
    codes = rc.generate_recovery_codes("u1")
    assert rc.verify_recovery_code("u1", codes[0]) is True     # first use ok
    assert rc.verify_recovery_code("u1", codes[0]) is False    # one-time -> reused fails


def test_verify_rejects_wrong_code(monkeypatch):
    sb = FakeSB()
    monkeypatch.setattr(rc, "supabase_admin", sb)
    rc.generate_recovery_codes("u1")
    assert rc.verify_recovery_code("u1", "AAAAA-BBBBB") is False


def test_verify_is_case_and_dash_insensitive(monkeypatch):
    sb = FakeSB()
    monkeypatch.setattr(rc, "supabase_admin", sb)
    codes = rc.generate_recovery_codes("u1")
    munged = codes[0].lower().replace("-", " ")
    assert rc.verify_recovery_code("u1", munged) is True


def test_regeneration_invalidates_old_unused(monkeypatch):
    sb = FakeSB()
    monkeypatch.setattr(rc, "supabase_admin", sb)
    old = rc.generate_recovery_codes("u1")
    rc.generate_recovery_codes("u1")           # regenerate -> old unused deleted
    assert rc.verify_recovery_code("u1", old[0]) is False


def test_empty_code_rejected(monkeypatch):
    sb = FakeSB()
    monkeypatch.setattr(rc, "supabase_admin", sb)
    rc.generate_recovery_codes("u1")
    assert rc.verify_recovery_code("u1", "") is False
    assert rc.verify_recovery_code("u1", "----") is False
