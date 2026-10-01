"""Infrastructure tests. Run: python -m unittest discover -s tests -v"""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests import fixtures  # noqa: E402

from factory import agents, books, core, locks, orchestrator, publishing, qc, states, tasks  # noqa: E402
from factory.core import FactoryError  # noqa: E402

REPO = fixtures.REPO


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixtures.sandbox()
        core.set_root(self.root)
        agents.register("AGENT-A", "SOCIO-1")
        agents.register("AGENT-B", "DANI")

    def tearDown(self):
        core.set_root(REPO)
        shutil.rmtree(self.root, ignore_errors=True)

    def run_step(self, agent, book_id, expect_type):
        t = tasks.claim_next(agent, book_id=book_id, include_auto=(expect_type == "FORMAT"))
        self.assertIsNotNone(t, f"no task for {book_id}, book={books.load(book_id)['status']}")
        self.assertEqual(t["type"], expect_type)
        if expect_type == "FORMAT":
            from factory import build
            build.build_all(book_id)
        else:
            fixtures.write_step(self.root, book_id, expect_type)
            if expect_type == "DESIGN":
                from factory import build
                build.render_cover(book_id)
        r = tasks.complete(t["task_id"], agent)
        self.assertEqual(r["result"], "DONE", r)
        orchestrator.orchestrate()
        return r


class TestStateMachine(Base):
    def test_invalid_transition_rejected(self):
        b = books.create("x", "en-US")
        with self.assertRaises(FactoryError):
            books.transition(b["id"], "APPROVED", "T", "cheat")

    def test_every_transition_logged(self):
        b = books.create("x", "en-US")
        books.transition(b["id"], "RESEARCH_PENDING", "T", "go")
        h = books.history(b["id"])
        self.assertEqual([x["to"] for x in h], ["IDEA", "RESEARCH_PENDING"])
        for rec in h:
            for k in ("ts", "agent", "action", "result"):
                self.assertIn(k, rec)

    def test_ids_unique_and_stable(self):
        ids = {books.create(f"t{i}", "es")["id"] for i in range(5)}
        self.assertEqual(len(ids), 5)
        self.assertTrue(all(i.startswith("EB-") for i in ids))

    def test_risk_detection(self):
        self.assertEqual(books.create("Keto diet for diabetics", "en-US")["risk_level"], "HIGH")
        self.assertEqual(books.create("Productivity for beginners", "en-US")["risk_level"], "LOW")


class TestLocks(Base):
    def test_exclusive_and_expiry(self):
        self.assertTrue(locks.acquire("r1", "AGENT-A", ttl_minutes=60))
        self.assertFalse(locks.acquire("r1", "AGENT-B", ttl_minutes=60))
        with self.assertRaises(FactoryError):
            locks.release("r1", "AGENT-B")
        # simulate abandoned lock
        lk = locks.read_lock("r1"); lk["expires_at"] = "2000-01-01T00:00:00Z"
        core.write_json(locks._lock_path("r1"), lk)
        self.assertTrue(locks.acquire("r1", "AGENT-B"))
        self.assertEqual(locks.read_lock("r1")["agent"], "AGENT-B")


class TestQueue(Base):
    def _book_at_research(self):
        b = books.create("Productivity", "en-US", book_id="EB-TEST-900")
        orchestrator.orchestrate()
        return b["id"]

    def test_no_duplicate_tasks(self):
        bid = self._book_at_research()
        orchestrator.orchestrate(); orchestrator.orchestrate()
        self.assertEqual(len(tasks.open_tasks_for_book(bid)), 1)

    def test_one_agent_per_book(self):
        bid = self._book_at_research()
        t = tasks.claim_next("AGENT-A")
        self.assertEqual(t["book_id"], bid)
        self.assertIsNone(tasks.claim_next("AGENT-B"))
        self.assertEqual(books.load(bid)["status"], "RESEARCHING")

    def test_validation_failure_is_retry_then_blocked(self):
        bid = self._book_at_research()
        for i in range(core.load_config()["max_retries"]):
            t = tasks.claim_next("AGENT-A")
            self.assertIsNotNone(t)
            r = tasks.complete(t["task_id"], "AGENT-A")  # no outputs written -> validation fails
            self.assertIn(r["result"], ("RETRY", "BLOCKED"))
        self.assertEqual(r["result"], "BLOCKED")
        self.assertEqual(books.load(bid)["status"], "BLOCKED")
        self.assertIsNone(tasks.claim_next("AGENT-A"))
        tasks.unblock(t["task_id"], "SOCIO-1", "retry")
        self.assertEqual(books.load(bid)["status"], "RESEARCH_PENDING")

    def test_release_does_not_count_retry(self):
        self._book_at_research()
        t = tasks.claim_next("AGENT-A")
        tasks.release(t["task_id"], "AGENT-A", "usage_limit")
        st, t2 = tasks.find(t["task_id"])
        self.assertEqual((st, t2["retry_count"]), ("READY", 0))

    def test_recover_stale_running(self):
        bid = self._book_at_research()
        t = tasks.claim_next("AGENT-A")
        lk = locks.read_lock(locks.book_resource(bid)); lk["expires_at"] = "2000-01-01T00:00:00Z"
        core.write_json(locks._lock_path(locks.book_resource(bid)), lk)
        Path(self.root, "BOOKS", bid, "junk.json.123.tmp").write_text("x")
        rep = orchestrator.recover()
        self.assertEqual(len(rep["stale_running"]), 1)
        self.assertEqual(tasks.find(t["task_id"])[0], "READY")
        self.assertEqual(books.load(bid)["status"], "RESEARCH_PENDING")
        self.assertTrue(rep["tmp_removed"])
        self.assertEqual(orchestrator.check_integrity(), [])

    def test_wip_limit(self):
        cfg = core.read_json(Path(self.root, "CONFIG", "factory.json")); cfg["max_active_books"] = 2
        core.write_json(Path(self.root, "CONFIG", "factory.json"), cfg)
        for i in range(4):
            books.create(f"t{i}", "en-US")
        orchestrator.orchestrate()
        self.assertEqual(sum(1 for b in books.all_books() if b["status"] == "IDEA"), 2)


class TestQC(Base):
    def test_qc_catches_placeholders_and_agent_text(self):
        issues = qc.text_issues("Intro. TODO add example. As an AI language model I think. See PROMPTS/WRITE.md")
        kinds = {k for k, _ in issues}
        self.assertEqual(kinds, {"placeholder", "internal_reference"})
        self.assertEqual(qc.text_issues("Lo hice todo bien, todo el día."), [])

    def test_language_detection(self):
        self.assertEqual(qc.detect_language("the and of to is you that it for with your this are " * 3), "en")
        self.assertEqual(qc.detect_language("el la de que y en los las es por para con una " * 3), "es")


class TestFullPipeline(Base):
    PIPE = ["RESEARCH", "BRIEF", "WRITE", "EDIT", "FACT_CHECK", "METADATA", "DESIGN", "FORMAT", "QC"]

    def test_pipeline_to_ready_for_publishing(self):
        b = books.create("Pipeline", "en-US", book_id="EB-TEST-901")
        orchestrator.orchestrate()
        for step in self.PIPE:
            self.run_step("AGENT-A", b["id"], step)
        self.assertEqual(books.load(b["id"])["status"], "HUMAN_REVIEW")
        self.assertTrue(Path(self.root, "BOOKS", b["id"], "review", "HUMAN_REVIEW.md").exists())
        publishing.approve(b["id"], "SOCIO-1", author="Test Author")
        bk = books.load(b["id"])
        self.assertEqual(bk["status"], "READY_FOR_PUBLISHING")
        pkg = Path(self.root, "BOOKS", b["id"], bk["files"]["publishing_package"])
        names = {p.name for p in pkg.iterdir()}
        self.assertTrue({"CHECKLIST.md", "metadata.json", "description.md", "keywords.txt"} <= names)
        self.assertTrue(any(n.endswith(".epub") for n in names))
        with self.assertRaises(FactoryError):
            publishing.release(b["id"], "SOCIO-1")  # never overwrite a final version
        self.assertEqual(orchestrator.check_integrity(), [])

    def test_two_books_two_agents_no_mixing(self):
        b2 = books.create("Two", "en-US", book_id="EB-TEST-002")
        b3 = books.create("Three", "en-GB", book_id="EB-TEST-003")
        orchestrator.orchestrate()
        for step in self.PIPE:
            ta = tasks.claim_next("AGENT-A", include_auto=step == "FORMAT")
            tb = tasks.claim_next("AGENT-B", include_auto=step == "FORMAT")
            self.assertNotEqual(ta["book_id"], tb["book_id"])
            for agent, t in (("AGENT-A", ta), ("AGENT-B", tb)):
                if step == "FORMAT":
                    from factory import build
                    build.build_all(t["book_id"])
                else:
                    fixtures.write_step(self.root, t["book_id"], step)
                    if step == "DESIGN":
                        from factory import build
                        build.render_cover(t["book_id"])
            self.assertEqual(tasks.complete(ta["task_id"], "AGENT-A")["result"], "DONE")
            self.assertEqual(tasks.complete(tb["task_id"], "AGENT-B")["result"], "DONE")
            orchestrator.orchestrate()
        for bid in ("EB-TEST-002", "EB-TEST-003"):
            self.assertEqual(books.load(bid)["status"], "HUMAN_REVIEW")
            final = Path(self.root, "BOOKS", bid, "manuscript", "final.md").read_text(encoding="utf-8")
            other = "EB-TEST-003" if bid == "EB-TEST-002" else "EB-TEST-002"
            self.assertIn(fixtures.marker(bid), final)
            self.assertNotIn(fixtures.marker(other), final)
        self.assertEqual(orchestrator.check_integrity(), [])

    def test_translation_creates_linked_edition(self):
        b = books.create("Pipeline", "en-US", target_languages=["es"])
        orchestrator.orchestrate()
        for step in self.PIPE[:5]:
            self.run_step("AGENT-A", b["id"], step)
        kids = [x for x in books.all_books() if x.get("translated_from") == b["id"]]
        self.assertEqual(len(kids), 1)
        self.assertEqual((kids[0]["language"], kids[0]["status"], kids[0]["parent_book"]), ("es-ES", "TRANSLATION_PENDING", b["id"]))
        orchestrator.orchestrate()
        self.assertEqual(len([x for x in books.all_books() if x.get("translated_from") == b["id"]]), 1)


class TestConcurrentClaims(Base):
    def test_race_exactly_one_winner(self):
        """6 separate OS processes race for 1 task: exactly one must win."""
        books.create("Race", "en-US", book_id="EB-TEST-950")
        orchestrator.orchestrate()
        ids = [f"RACER-{i:02d}" for i in range(6)]
        for i in ids:
            agents.register(i, "test")
        env = {**os.environ, "EBF_ROOT": str(self.root)}
        procs = [subprocess.Popen([sys.executable, str(REPO / "factory.py"), "next", "--agent", i], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8") for i in ids]
        results = [json.loads(p.communicate(timeout=60)[0]) for p in procs]
        winners = [r for r in results if r.get("task")]
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(len(tasks.all_tasks(["RUNNING"])), 1)
        self.assertEqual(orchestrator.check_integrity(), [])


if __name__ == "__main__":
    unittest.main()


class TestGitMultiMachine(unittest.TestCase):
    """Two clones (= two machines, e.g. Socio 1 and Dani) claim the same task at the same time."""

    def git(self, cwd, *args):
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_claim_conflict_resolved_by_git(self):
        from factory import gitsync
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="ebf-git-"))
        try:
            remote = tmp / "remote.git"
            self.git(tmp, "init", "-q", "--bare", "-b", "main", str(remote))
            a = fixtures.sandbox()
            cfg = json.loads((a / "CONFIG" / "factory.json").read_text()); cfg["git"]["sync_enabled"] = True
            (a / "CONFIG" / "factory.json").write_text(json.dumps(cfg))
            shutil.copy(REPO / ".gitattributes", a / ".gitattributes")
            core.set_root(a)
            agents.register("AGENT-A", "SOCIO-1")
            agents.register("AGENT-B", "DANI")
            books.create("Git race", "en-US", book_id="EB-TEST-960")
            orchestrator.orchestrate()
            self.git(a, "init", "-q", "-b", "main"); self.git(a, "add", "-A"); self.git(a, "commit", "-q", "-m", "init")
            self.git(a, "remote", "add", "origin", str(remote)); self.git(a, "push", "-q", "-u", "origin", "main")
            b = tmp / "cloneB"
            self.git(tmp, "clone", "-q", str(remote), str(b))
            # both machines claim locally before either pushes
            ta = tasks.claim_next("AGENT-A")
            core.set_root(b)
            tb = tasks.claim_next("AGENT-B")
            self.assertEqual(ta["task_id"], tb["task_id"])
            core.set_root(a)
            self.assertTrue(gitsync.publish_claim("AGENT-A", ta["task_id"]))
            core.set_root(b)
            self.assertFalse(gitsync.publish_claim("AGENT-B", tb["task_id"]))
            st, t = tasks.find(ta["task_id"])
            self.assertEqual((st, t["assigned_agent"]), ("RUNNING", "AGENT-A"))  # B now sees A's claim
            self.assertEqual(orchestrator.check_integrity(), [])
        finally:
            core.set_root(REPO)
            shutil.rmtree(tmp, ignore_errors=True)
