"""Tests for templates/adapters/: the entry points and commit gates a consuming repository copies in.

Run from the repository root:
    python -m unittest discover -s tests -v
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ADAPTERS = REPO / "templates" / "adapters"
BROKEN = REPO / "examples" / "broken"
SKILL = ADAPTERS / "skills" / "dds" / "SKILL.md"
SETTINGS = ADAPTERS / "claude-code" / "settings.json"
PRE_COMMIT = ADAPTERS / "git" / "pre-commit"

# fields of the open Agent Skills specification (agentskills.io/specification)
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


def find_bash():
    """Git Bash first: on Windows, `bash` on PATH is often the WSL launcher in System32, which is not a shell."""
    git = shutil.which("git")
    if git:
        for parent in list(Path(git).resolve().parents)[:4]:
            for cand in (parent / "bin" / "bash.exe", parent / "usr" / "bin" / "bash.exe", parent / "bin" / "bash"):
                if cand.exists():
                    return str(cand)
    bash = shutil.which("bash")
    if bash and "system32" in bash.lower():
        return None
    return bash


def frontmatter_top_level_keys(text):
    body = text.split("---")[1]
    return {ln.split(":", 1)[0] for ln in body.splitlines() if ln.strip() and not ln.startswith((" ", "\t"))}


class SkillFile(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")

    def test_frontmatter_uses_only_spec_fields(self):
        keys = frontmatter_top_level_keys(self.text)
        self.assertTrue(keys <= SPEC_FIELDS, "non-spec fields: %s" % (keys - SPEC_FIELDS))
        self.assertIn("name", keys)
        self.assertIn("description", keys)

    def test_name_matches_directory_and_grammar(self):
        name = re.search(r"^name: (.+)$", self.text, re.M).group(1).strip()
        self.assertEqual(name, SKILL.parent.name)
        self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(name), 64)

    def test_description_length_and_triggers(self):
        desc = re.search(r"^description: (.+)$", self.text, re.M).group(1)
        self.assertTrue(1 <= len(desc) <= 1024)
        for trigger in ("commit", ".dds", "feature", "documentation"):
            self.assertIn(trigger, desc)

    def test_body_points_at_the_sources_of_truth(self):
        for ref in (".dds/meta/manifesto.dds.md", ".dds/meta/adopt.dds.md", "dds.py check --gate", "impact <id> --down"):
            self.assertIn(ref, self.text)
        self.assertLess(self.text.count("\n"), 40, "the skill is a router; keep it short")

    def test_dds_version_matches_script(self):
        script = (REPO / ".dds" / "meta" / "scripts" / "dds.py").read_text(encoding="utf-8")
        version = re.search(r'^DDS_VERSION = "([^"]+)"', script, re.M).group(1)
        self.assertIn('dds_version: "%s"' % version, self.text)


class RepositoryDogfood(unittest.TestCase):
    """The DDS repository installs its own adapters: entry files, hook, and the skill in both placements."""

    def test_skill_installed_in_both_placements_and_identical_to_template(self):
        import filecmp
        for placement in (REPO / ".claude" / "skills" / "dds" / "SKILL.md", REPO / ".agents" / "skills" / "dds" / "SKILL.md"):
            with self.subTest(placement=str(placement.relative_to(REPO))):
                self.assertTrue(placement.exists(), "%s missing" % placement)
                self.assertTrue(filecmp.cmp(str(SKILL), str(placement), shallow=False), "%s drifted from the template" % placement)

    def test_hook_installed_and_identical_to_template(self):
        import filecmp
        self.assertTrue(filecmp.cmp(str(SETTINGS), str(REPO / ".claude" / "settings.json"), shallow=False))
        self.assertEqual((REPO / "CLAUDE.md").read_text(encoding="utf-8").splitlines()[0], "@AGENTS.md")


class EntryFiles(unittest.TestCase):
    def test_agents_md_carries_the_four_steps(self):
        text = (ADAPTERS / "AGENTS.md").read_text(encoding="utf-8")
        for ref in (".dds/meta/manifesto.dds.md", ".dds/meta/adopt.dds.md", ".dds/product/constraints.dds.md",
                    "check --gate", "RESULT: PASS"):
            self.assertIn(ref, text)
        self.assertLess(text.count("\n"), 25, "AGENTS.md is always loaded; every line costs")

    def test_claude_md_imports_agents_md_first(self):
        first = next(ln for ln in (ADAPTERS / "CLAUDE.md").read_text(encoding="utf-8").splitlines() if ln.strip())
        self.assertEqual(first, "@AGENTS.md")

    def test_ci_template_runs_the_gate(self):
        text = (ADAPTERS / "ci" / "dds-check.yml").read_text(encoding="utf-8")
        self.assertIn("python .dds/meta/scripts/dds.py check --gate", text)


class ClaudeHook(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads(SETTINGS.read_text(encoding="utf-8"))
        self.handlers = self.cfg["hooks"]["PreToolUse"][0]["hooks"]
        self.hook = self.handlers[0]

    def test_shape(self):
        self.assertEqual(self.cfg["hooks"]["PreToolUse"][0]["matcher"], "Bash")
        patterns = {h["if"] for h in self.handlers}
        self.assertEqual(patterns, {"Bash(git commit*)", "Bash(git -C * commit*)", "Bash(git -c * commit*)"}, "plain, -C and -c commit forms")
        for h in self.handlers:
            self.assertEqual(h["type"], "command")
            self.assertIn("check --gate --staged", h["command"])
            self.assertIn("exit 2", h["command"], "only exit 2 blocks a PreToolUse hook")
            self.assertIn("DDS_PYTHON", h["command"], "interpreter fallback mirrors the git hook")
        self.assertEqual(len({h["command"] for h in self.handlers}), 1, "both forms run the same gate")

    def _run_hook(self, project_dir):
        bash = find_bash()
        if not bash:
            self.skipTest("Git Bash not available")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
        proc = subprocess.run([bash, "-c", self.hook["command"]], env=env, capture_output=True, text=True, encoding="utf-8")
        return proc.returncode, proc.stdout + proc.stderr

    def test_hook_blocks_with_a_truthful_message_when_no_interpreter_is_found(self):
        bash = find_bash()
        if not bash:
            self.skipTest("Git Bash not available")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(REPO), PATH="/usr/bin:/bin")
        env.pop("DDS_PYTHON", None)
        proc = subprocess.run([bash, "-c", self.hook["command"]], env=env, capture_output=True, text=True, encoding="utf-8")
        if "python not found" not in proc.stdout + proc.stderr and proc.returncode == 0:
            self.skipTest("a python is reachable from /usr/bin:/bin on this machine")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("python not found", proc.stdout + proc.stderr)
        self.assertNotIn("clear the ERROR lines", proc.stdout + proc.stderr, "the failure message must not blame the documents")

    def test_hook_passes_on_template_and_blocks_on_broken(self):
        code, out = self._run_hook(REPO)
        self.assertEqual(code, 0, out)
        code, out = self._run_hook(BROKEN)
        self.assertEqual(code, 2, "a failing gate must exit 2 to block the commit:\n" + out)
        self.assertIn("DDS gate", out)


class GitPreCommit(unittest.TestCase):
    """Real git repository, hooksPath installed, gate: warn lets a failing commit through, gate: strict blocks it."""

    def setUp(self):
        self.git = shutil.which("git")
        if not self.git:
            self.skipTest("git not available")
        self.tmp = Path(tempfile.mkdtemp(prefix="dds-hook-"))
        shutil.copytree(REPO / ".dds", self.tmp / ".dds", ignore=shutil.ignore_patterns(".locks", "__pycache__"))
        hooks = self.tmp / ".githooks"
        hooks.mkdir()
        target = hooks / "pre-commit"
        shutil.copy(PRE_COMMIT, target)
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self._git("init", "-q")
        self._git("config", "core.autocrlf", "false")
        self._git("config", "core.hooksPath", ".githooks")
        self._git("config", "user.email", "t@t")
        self._git("config", "user.name", "t")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _git(self, *args):
        return subprocess.run([self.git] + list(args), cwd=str(self.tmp), capture_output=True, text=True, encoding="utf-8")

    def _set_gate(self, value):
        tree = self.tmp / ".dds" / "tree.dds.md"
        tree.write_text(re.sub(r"^gate: .*$", "gate: %s" % value, tree.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")

    def _break_tree(self):
        (self.tmp / ".dds" / "product" / "stray.dds.md").write_text(
            "---\nid: product-stray\ntype: product\nstatus: active\ndependencies: []\nlast_updated: 2026-09-18\n"
            "description: Never indexed, so the gate fails.\n---\n\n# STRAY\n", encoding="utf-8")

    def test_clean_tree_commits(self):
        self._git("add", "-A")
        proc = self._git("commit", "-q", "-m", "clean")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_warn_gate_lets_a_failing_commit_through(self):
        self._set_gate("warn")
        self._break_tree()
        self._git("add", "-A")
        proc = self._git("commit", "-q", "-m", "broken under warn")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("gate is 'warn'", proc.stderr)
        self.assertIn("indexed 0 time(s)", proc.stdout + proc.stderr)

    def test_strict_gate_blocks_code_committed_without_its_document(self):
        """The pre-commit runs --staged: code under an active module document needs that document in the commit."""
        self._set_gate("strict")
        (self.tmp / ".dds" / "product" / "constraints.dds.md").write_text(
            "---\nid: product-constraints\ntype: product\nstatus: active\ndependencies: []\nlast_updated: 2026-09-21\n"
            "description: Constraints.\n---\n\n# PRODUCT: Constraints\n\n## [0] BUSINESS_VISION_AND_VALUE\nProtect users.\n\n"
            "## [1] CONSTRAINTS\n<constraints>\n- **C1 (security):** The system MUST hash passwords. Source: SEC-1.\n</constraints>\n\n"
            "## [2] KEY_PERFORMANCE_INDICATORS (KPIs)\nNone.\n", encoding="utf-8")
        ptree = self.tmp / ".dds" / "product" / "product.tree.dds.md"
        ptree.write_text(ptree.read_text(encoding="utf-8").replace(
            "<!-- No documents yet. Entries are appended by dds.product/write.dds.md [4]. -->", "- [constraints.dds.md]: Constraints."), encoding="utf-8")
        (self.tmp / "src" / "auth").mkdir(parents=True)
        (self.tmp / "src" / "auth" / "login.py").write_text("def login(): pass\n", encoding="utf-8")
        mod = self.tmp / ".dds" / "modules" / "auth"
        mod.mkdir()
        (mod / "auth.tree.dds.md").write_text(
            "---\nid: tree-modules-auth\ntype: tree\nstatus: active\ndependencies: []\nlast_updated: 2026-09-21\n"
            "description: Auth index.\n---\n\n# AUTH_TREE\n\n- [login.dds.md]: Login flow.\n", encoding="utf-8")
        (mod / "login.dds.md").write_text(
            "---\nid: modules-auth-login\ntype: module\nstatus: active\ndependencies: []\nsources: [src/auth/**]\n"
            "last_updated: 2026-09-21\ndescription: Login flow.\n---\n\n# AUTH: Login\n\n## [0] CONTEXT_AND_PURPOSE\nThe handler logs users in.\n\n"
            "## [1] TECHNICAL_CONSTRAINTS\n<constraints>\n- The handler MUST hash passwords.\n</constraints>\n\n## [2] LOGIC_FLOW\n1. Verify.\n", encoding="utf-8")
        mtree = self.tmp / ".dds" / "modules" / "modules.tree.dds.md"
        mtree.write_text(mtree.read_text(encoding="utf-8").replace(
            "<!-- No documents yet. Domain folders are registered by dds.modules/write.dds.md [4]. -->", "- [auth/]: Auth domain."), encoding="utf-8")
        self._git("add", "-A")
        proc = self._git("commit", "-q", "-m", "governed baseline")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        (self.tmp / "src" / "auth" / "login.py").write_text("def login(): return True\n", encoding="utf-8")
        self._git("add", "-A")
        proc = self._git("commit", "-q", "-m", "code only")
        self.assertNotEqual(proc.returncode, 0, "strict gate must block code committed without its document")
        self.assertIn("staged code under sources (src/auth/login.py) without this document", proc.stdout + proc.stderr)

    def test_strict_gate_blocks_a_failing_commit(self):
        self._set_gate("strict")
        # strict also requires an active product-constraints document; the broken tree lacks it on purpose
        self._break_tree()
        self._git("add", "-A")
        proc = self._git("commit", "-q", "-m", "broken under strict")
        self.assertNotEqual(proc.returncode, 0, "strict gate must block")
        self.assertIn("gate is 'strict'", proc.stderr)
        log = self._git("log", "--oneline")
        self.assertEqual(log.stdout.strip(), "", "nothing may be committed when the strict gate fails")


if __name__ == "__main__":
    unittest.main(verbosity=2)
