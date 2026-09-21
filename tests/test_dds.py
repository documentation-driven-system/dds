"""Tests for .dds/meta/scripts/dds.py.

Run from the repository root:
    python -m unittest discover -s tests -v

Standard library only. The positive fixture is the repository's own .dds/ template;
the negative fixture is examples/broken/ with its EXPECTED*.txt files.
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / ".dds" / "meta" / "scripts" / "dds.py"
BROKEN = REPO / "examples" / "broken"


def run(*args, root=None, cwd=None):
    cmd = [sys.executable, str(SCRIPT)]
    if root is not None:
        cmd += ["--root", str(root)]
    cmd += list(args)
    proc = subprocess.run(cmd, cwd=str(cwd or REPO), capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, proc.stdout + proc.stderr


def load_module():
    spec = importlib.util.spec_from_file_location("dds", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TemplateTree(unittest.TestCase):
    def test_template_passes_gate_check(self):
        code, out = run("check", "--gate", root=REPO)
        self.assertEqual(code, 0, out)
        self.assertIn("RESULT: PASS", out)
        self.assertNotIn("ERROR:", out)

    def test_coverage_and_sync_degrade_to_info_without_sources(self):
        code, out = run("check", "--coverage", "--sync", root=REPO)
        self.assertEqual(code, 0, out)
        self.assertIn("INFO: coverage:", out)
        self.assertIn("INFO: sync:", out)

    def test_tree_renders_root_and_domains(self):
        code, out = run("tree", root=REPO)
        self.assertEqual(code, 0, out)
        for t in (".dds/tree.dds.md", ".dds/product/product.tree.dds.md",
                  ".dds/architecture/architecture.tree.dds.md", ".dds/modules/modules.tree.dds.md"):
            self.assertIn(t, out)

    def test_impact_direct_down_up(self):
        code, out = run("impact", "meta-manifesto", root=REPO)
        self.assertEqual(code, 0, out)
        self.assertIn("meta-schema\tactive\tmeta", out)
        self.assertNotIn("meta-product-write", out, "direct dependents must not include depth-2 documents")
        code, out = run("impact", "meta-manifesto", "--down", root=REPO)
        self.assertEqual(code, 0, out)
        self.assertIn("2\tmeta-product-write\tactive\tmeta", out)
        code, out = run("impact", "meta-product-update", "--up", root=REPO)
        self.assertEqual(code, 0, out)
        self.assertIn("meta-product-rules\tactive", out)
        self.assertIn("meta-product-write\tactive", out)

    def test_impact_unknown_id_is_usage_error(self):
        code, out = run("impact", "product-does-not-exist", root=REPO)
        self.assertEqual(code, 2)
        self.assertIn("unknown id", out)


class BrokenFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.out = run("check", "--gate", root=BROKEN)

    def test_broken_fails(self):
        self.assertEqual(self.code, 1, self.out)
        self.assertIn("RESULT: FAIL", self.out)

    def test_every_expected_error_is_reported(self):
        missing = [line for line in (BROKEN / "EXPECTED.txt").read_text(encoding="utf-8").splitlines()
                   if line.strip() and line not in self.out]
        self.assertEqual(missing, [], "expected errors not reported:\n" + "\n".join(missing) + "\n\n" + self.out)

    def test_every_expected_warning_is_reported(self):
        missing = [line for line in (BROKEN / "EXPECTED_WARN.txt").read_text(encoding="utf-8").splitlines()
                   if line.strip() and line not in self.out]
        self.assertEqual(missing, [], "expected warnings not reported:\n" + "\n".join(missing))

    def test_lock_is_info_without_gate(self):
        code, out = run("check", root=BROKEN)
        self.assertEqual(code, 1)
        self.assertIn("INFO: .dds/modules/auth/login.dds.md: lock present", out)
        self.assertNotIn("ERROR: .dds/modules/auth/login.dds.md: lock present", out)

    def test_out_of_folder_entry_does_not_count_as_indexing(self):
        self.assertNotIn("vision.dds.md: indexed 2 time(s)", self.out)


class LockLifecycle(unittest.TestCase):
    """Copy the template, switch locking on, and walk lock -> refused -> takeover -> unlock."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dds-lock-"))
        shutil.copytree(REPO / ".dds", self.tmp / ".dds", ignore=shutil.ignore_patterns(".locks"))
        tree = self.tmp / ".dds" / "tree.dds.md"
        tree.write_text(tree.read_text(encoding="utf-8").replace("locking: off", "locking: on"), encoding="utf-8")
        self.target = self.tmp / ".dds" / "meta" / "adopt.dds.md"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_lock_cycle(self):
        code, out = run("lock", str(self.target), "--by", "agent-a", root=self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("STATUS: LOCKED meta-adopt by agent-a", out)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("locked_by: agent-a", text)
        self.assertIn("locked_at: ", text)
        self.assertTrue((self.tmp / ".dds" / ".locks" / "meta-adopt.lock").exists())

        code, out = run("check", root=self.tmp)
        self.assertEqual(code, 0, "plain check must tolerate a lock:\n" + out)
        self.assertIn("INFO: .dds/meta/adopt.dds.md: lock present", out)
        code, out = run("check", "--gate", root=self.tmp)
        self.assertEqual(code, 1, "gate check must refuse a lock:\n" + out)

        code, out = run("lock", str(self.target), "--by", "agent-b", root=self.tmp)
        self.assertEqual(code, 1, out)
        self.assertIn("STATUS: LOCKED_BY agent-a", out)

        code, out = run("lock", str(self.target), "--by", "agent-a", root=self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("LOCK_REFRESHED", out)

        stale = (datetime.now(timezone.utc) - timedelta(minutes=41)).strftime("%Y-%m-%dT%H:%M:%SZ")
        (self.tmp / ".dds" / ".locks" / "meta-adopt.lock").write_text("agent-a\n%s\n" % stale, encoding="utf-8")
        code, out = run("lock", str(self.target), "--by", "agent-b", root=self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("LOCK_TAKEN_OVER from agent-a", out)
        self.assertIn("locked_by: agent-b", self.target.read_text(encoding="utf-8"))

        code, out = run("unlock", str(self.target), root=self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("STATUS: UNLOCKED meta-adopt (was held by agent-b)", out)
        text = self.target.read_text(encoding="utf-8")
        self.assertNotIn("locked_by", text)
        self.assertNotIn("locked_at", text)
        self.assertFalse((self.tmp / ".dds" / ".locks" / "meta-adopt.lock").exists())
        code, out = run("check", "--gate", root=self.tmp)
        self.assertEqual(code, 0, out)

    def test_lock_is_noop_when_locking_off(self):
        tree = self.tmp / ".dds" / "tree.dds.md"
        tree.write_text(tree.read_text(encoding="utf-8").replace("locking: on", "locking: off"), encoding="utf-8")
        code, out = run("lock", str(self.target), "--by", "agent-a", root=self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("STATUS: LOCKING_OFF", out)
        self.assertNotIn("locked_by", self.target.read_text(encoding="utf-8"))


class StagedGate(unittest.TestCase):
    """check --staged: code staged under an active document's sources requires that document to be staged too."""

    def setUp(self):
        self.git = shutil.which("git")
        if not self.git:
            self.skipTest("git not available")
        self.tmp = Path(tempfile.mkdtemp(prefix="dds-staged-"))
        shutil.copytree(REPO / "examples" / "task-tracker", self.tmp / "tt", ignore=shutil.ignore_patterns(".locks", "__pycache__"))
        self.root = self.tmp / "tt"
        self._git("init", "-q"); self._git("config", "core.autocrlf", "false")
        self._git("config", "user.email", "t@t"); self._git("config", "user.name", "t")
        self._git("add", "-A"); self._git("commit", "-q", "-m", "base")
        self.code = self.root / "src" / "tasks" / "complete.py"
        self.doc = self.root / ".dds" / "modules" / "tasks" / "complete-task.dds.md"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _git(self, *args):
        return subprocess.run([self.git] + list(args), cwd=str(self.root), capture_output=True, text=True, encoding="utf-8")

    def _touch(self, path, marker):
        path.write_text(path.read_text(encoding="utf-8") + "\n" + marker + "\n", encoding="utf-8")

    def test_code_without_its_document_fails_in_gate_mode_and_warns_otherwise(self):
        self._touch(self.code, "REOPEN_WINDOW_HOURS = 48  # behaviour change")
        self._git("add", "-A")
        code, out = run("check", "--gate", "--staged", root=self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR: .dds/modules/tasks/complete-task.dds.md: staged code under sources (src/tasks/complete.py) without this document", out)
        code, out = run("check", "--staged", root=self.root)
        self.assertEqual(code, 0, "without --gate the staged rule is a warning:\n" + out)
        self.assertIn("WARN: .dds/modules/tasks/complete-task.dds.md: staged code under sources", out)

    def test_code_with_its_document_passes(self):
        self._touch(self.code, "REOPEN_WINDOW_HOURS = 48")
        self._touch(self.doc, "- [2026-09-21]: Reopen window widened to 48 hours.")
        self._git("add", "-A")
        code, out = run("check", "--gate", "--staged", root=self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("RESULT: PASS", out)

    def test_nothing_staged_is_information_only(self):
        code, out = run("check", "--gate", "--staged", root=self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("INFO: staged: nothing is staged", out)

    def test_new_code_that_no_document_governs_is_gated_until_a_draft_exists(self):
        billing = self.root / "src" / "billing"
        billing.mkdir()
        (billing / "invoice.py").write_text("def invoice(): pass\n", encoding="utf-8")
        self._git("add", "-A")
        code, out = run("check", "--gate", "--staged", root=self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR: src/billing/invoice.py: staged code that no module document governs; create a draft document first (adopt.dds.md [2].3)", out)
        mod = self.root / ".dds" / "modules" / "billing"
        mod.mkdir()
        (mod / "billing.tree.dds.md").write_text(
            "---\nid: tree-modules-billing\ntype: tree\nstatus: active\ndependencies: []\nlast_updated: 2026-09-21\n"
            "description: Billing index.\n---\n\n# BILLING_TREE\n\n- [invoice.dds.md]: Invoicing, reverse-documented draft.\n", encoding="utf-8")
        (mod / "invoice.dds.md").write_text(
            "---\nid: modules-billing-invoice\ntype: module\nstatus: draft\ndependencies: []\nsources: [src/billing/**]\n"
            "last_updated: 2026-09-21\ndescription: Invoicing, reverse-documented from src/billing.\n---\n\n# BILLING: Invoice\n\n"
            "## [0] CONTEXT_AND_PURPOSE\nDocumented from code; not yet reviewed.\n", encoding="utf-8")
        mtree = self.root / ".dds" / "modules" / "modules.tree.dds.md"
        mtree.write_text(mtree.read_text(encoding="utf-8") + "- [billing/]: Invoicing.\n", encoding="utf-8")
        self._git("add", "-A")
        code, out = run("check", "--gate", "--staged", root=self.root)
        self.assertEqual(code, 0, "a draft document covering the new code opens the gate:\n" + out)

    def test_draft_documents_do_not_gate_their_code(self):
        self.doc.write_text(self.doc.read_text(encoding="utf-8").replace("status: active", "status: draft", 1), encoding="utf-8")
        self._git("add", "-A"); self._git("commit", "-q", "-m", "draft")
        self._touch(self.code, "REOPEN_WINDOW_HOURS = 48")
        self._git("add", "-A")
        code, out = run("check", "--gate", "--staged", root=self.root)
        self.assertEqual(code, 0, "a draft document is not authoritative, so its code is not gated:\n" + out)
        self.assertNotIn("staged code under sources", out)


class Hierarchy(unittest.TestCase):
    """Dependencies point upward and the graph is acyclic; the example copy is the fixture."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dds-hier-"))
        shutil.copytree(REPO / "examples" / "task-tracker", self.tmp / "tt", ignore=shutil.ignore_patterns(".locks", "__pycache__"))
        self.root = self.tmp / "tt"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _set_deps(self, rel, deps):
        p = self.root / rel
        text = re.sub(r"^dependencies: .*$", "dependencies: %s" % deps, p.read_text(encoding="utf-8"), count=1, flags=re.M)
        p.write_text(text, encoding="utf-8")

    def test_product_depending_on_a_module_is_rejected_as_reversed_and_cyclic(self):
        self._set_deps(".dds/product/vision.dds.md", "[architecture-tech-stack]")   # tech-stack already depends on vision
        code, out = run("check", "--gate", root=self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("depends on a lower tier: a product document may not depend on 'architecture-tech-stack' (architecture)", out)
        self.assertIn("dependency cycle: architecture-tech-stack -> product-vision -> architecture-tech-stack", out)

    def test_product_depending_on_product_is_allowed(self):
        self._set_deps(".dds/product/epics/task-management/task-management.dds.md", "[product-vision]")
        code, out = run("check", "--gate", root=self.root)
        self.assertEqual(code, 0, out)

    def test_empty_active_module_with_unmatched_sources_is_rejected(self):
        mod = self.root / ".dds" / "modules" / "tasks" / "empty.dds.md"
        mod.write_text("---\nid: modules-tasks-empty\ntype: module\nstatus: active\ndependencies: []\n"
                       "sources: [src/does-not-exist/**]\nlast_updated: 2026-09-21\ndescription: Empty on purpose.\n---\n\n# TASKS: Empty\n",
                       encoding="utf-8")
        tree = self.root / ".dds" / "modules" / "tasks" / "tasks.tree.dds.md"
        tree.write_text(tree.read_text(encoding="utf-8") + "- [empty.dds.md]: Empty on purpose.\n", encoding="utf-8")
        code, out = run("check", "--gate", root=self.root)
        self.assertEqual(code, 1, out)
        for msg in ("active document is missing section [0]", "active document is missing section [1]",
                    "active document is missing section [2]", "sources glob 'src/does-not-exist/**' matches no file"):
            self.assertIn(msg, out)
        mod.write_text(mod.read_text(encoding="utf-8").replace("status: active", "status: draft", 1), encoding="utf-8")
        code, out = run("check", "--gate", root=self.root)
        self.assertEqual(code, 0, "the same document as a draft only warns:\n" + out)
        self.assertIn("WARN: .dds/modules/tasks/empty.dds.md: draft document is missing section [1]", out)


class GlobTranslation(unittest.TestCase):
    def test_globs(self):
        dds = load_module()
        cases = [
            ("src/auth/**", "src/auth/login.ts", True),
            ("src/auth/**", "src/auth/deep/er/x.py", True),
            ("src/auth/**", "src/authx/login.ts", False),
            ("**/*.ts", "a/b/c.ts", True),
            ("**/*.ts", "c.ts", True),
            ("**/*.ts", "a/b/c.tsx", False),
            ("src/*/index.js", "src/pay/index.js", True),
            ("src/*/index.js", "src/pay/deep/index.js", False),
            ("a/**/b.md", "a/b.md", True),
            ("a/**/b.md", "a/x/y/b.md", True),
        ]
        for pat, path, expected in cases:
            with self.subTest(pat=pat, path=path):
                self.assertEqual(bool(dds.glob_to_regex(pat).match(path)), expected)


class SyncAndCoverage(unittest.TestCase):
    """A tiny repo with code + one module doc: coverage counts, sync warns on drift."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dds-sync-"))
        shutil.copytree(REPO / ".dds", self.tmp / ".dds", ignore=shutil.ignore_patterns(".locks"))
        (self.tmp / "src" / "auth").mkdir(parents=True)
        (self.tmp / "src" / "auth" / "login.ts").write_text("export const a = 1;\n", encoding="utf-8")
        (self.tmp / "src" / "billing").mkdir()
        (self.tmp / "src" / "billing" / "invoice.ts").write_text("export const b = 2;\n", encoding="utf-8")
        mod = self.tmp / ".dds" / "modules" / "auth"
        mod.mkdir()
        (mod / "auth.tree.dds.md").write_text(
            "---\nid: tree-modules-auth\ntype: tree\nstatus: active\ndependencies: []\nlast_updated: 2026-09-18\n"
            "description: Auth index.\n---\n\n# AUTH_TREE\n\n- [login.dds.md]: Login flow.\n", encoding="utf-8")
        (mod / "login.dds.md").write_text(
            "---\nid: modules-auth-login\ntype: module\nstatus: active\ndependencies: []\nsources: [src/auth/**]\n"
            "last_updated: 2026-09-18\ndescription: Login flow.\n---\n\n# AUTH: Login\n\n"
            "## [0] CONTEXT_AND_PURPOSE\nThe login handler issues sessions.\n\n"
            "## [1] TECHNICAL_CONSTRAINTS\n<constraints>\n- The handler MUST hash passwords.\n</constraints>\n\n"
            "## [2] LOGIC_FLOW\n1. The handler verifies the password.\n", encoding="utf-8")
        mt = self.tmp / ".dds" / "modules" / "modules.tree.dds.md"
        mt.write_text(mt.read_text(encoding="utf-8") + "\n- [auth/]: Auth domain.\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_coverage_reports_everything_ungoverned_before_the_first_module_document(self):
        """adopt.dds.md [2].4 relies on this report on day one, when no module document exists yet."""
        import shutil as _sh
        _sh.rmtree(self.tmp / ".dds" / "modules" / "auth")
        mt = self.tmp / ".dds" / "modules" / "modules.tree.dds.md"
        mt.write_text(mt.read_text(encoding="utf-8").replace("\n- [auth/]: Auth domain.\n", "\n"), encoding="utf-8")
        code, out = run("check", "--coverage", root=self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("0/2 code files covered by module sources (0%)", out)
        self.assertIn("no module document declares sources: yet", out)
        self.assertIn("WARN: coverage: src/auth: 1 code file(s) not governed", out)

    def test_coverage_reports_ungoverned_directory(self):
        code, out = run("check", "--coverage", root=self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("1/2 code files covered by module sources (50%)", out)
        self.assertIn("WARN: coverage: src/billing: 1 code file(s) not governed", out)

    def test_sync_warns_when_sources_change_but_doc_does_not(self):
        git = shutil.which("git")
        if not git:
            self.skipTest("git not available")
        subprocess.run([git, "init", "-q"], cwd=str(self.tmp), check=True)
        subprocess.run([git, "config", "core.autocrlf", "false"], cwd=str(self.tmp), check=True)
        subprocess.run([git, "add", "-A"], cwd=str(self.tmp), check=True)
        subprocess.run([git, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
                       cwd=str(self.tmp), check=True)
        (self.tmp / "src" / "auth" / "login.ts").write_text("export const a = 2;\n", encoding="utf-8")
        code, out = run("check", "--sync", root=self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN: .dds/modules/auth/login.dds.md: sources changed (src/auth/login.ts) but this document was not touched", out)
        # touching the document silences the warning (documented limitation)
        doc = self.tmp / ".dds" / "modules" / "auth" / "login.dds.md"
        doc.write_text(doc.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        code, out = run("check", "--sync", root=self.tmp)
        self.assertNotIn("drift?", out)

    def test_sync_resolves_paths_when_project_is_below_git_toplevel(self):
        """Monorepo layout: git toplevel is tmp/, the DDS project lives in tmp/svc/."""
        git = shutil.which("git")
        if not git:
            self.skipTest("git not available")
        top = Path(tempfile.mkdtemp(prefix="dds-mono-"))
        try:
            svc = top / "svc"
            shutil.copytree(self.tmp, svc)
            subprocess.run([git, "init", "-q"], cwd=str(top), check=True)
            subprocess.run([git, "config", "core.autocrlf", "false"], cwd=str(top), check=True)
            subprocess.run([git, "add", "-A"], cwd=str(top), check=True)
            subprocess.run([git, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
                           cwd=str(top), check=True)
            (svc / "src" / "auth" / "login.ts").write_text("export const a = 3;\n", encoding="utf-8")
            code, out = run("check", "--sync", root=svc)
            self.assertEqual(code, 0, out)
            self.assertIn("sources changed (src/auth/login.ts)", out)
        finally:
            shutil.rmtree(top, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
