#!/usr/bin/env python3
"""dds.py - mechanical checks and operations for a Documentation-Driven System (.dds/) tree.

Command surface (frozen; see .dds/meta/manifesto.dds.md [4]):

  check [--gate] [--staged] [--coverage] [--sync]
                                         validate the whole .dds/ tree against schema.dds.md;
                                         --staged: staged code under an active document's sources
                                         requires that document to be staged too (error in gate mode)
  impact <id> [--up | --down]            dependency graph queries
  lock <file> --by <executor_id>         acquire a 40-minute lock (locking: on only)
  unlock <file>                          release a lock
  tree                                   render the index trees and report index problems

Global option: --root PATH  (directory that contains .dds/; default: nearest ancestor of cwd)

Standard library only. Written for Python 3.8+, tested on 3.14 (Git Bash and PowerShell on Windows).
Exit codes: 0 ok, 1 errors found / lock refused, 2 usage.
`check --gate` always exits 1 when errors exist; honouring `gate: warn` for humans is the commit
hook's decision (see templates/adapters/), not this script's. `unlock` ignores ownership by design
and prints the previous holder.
"""
import argparse
import os
import re
import subprocess
import sys
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

DDS_VERSION = "2.1.0"
LOCK_TIMEOUT_MIN = 40
CHANGELOG_CAP = 10
MAX_HEADER_DEPTH = 3

TYPES = {"product", "architecture", "module", "tree", "meta"}
STATUSES = {"draft", "active", "deprecated"}
PREFIX = {"product": "product-", "architecture": "architecture-", "module": "modules-",
          "tree": "tree-", "meta": "meta-"}
REQUIRED = ("id", "type", "status", "dependencies", "last_updated")
TIER_RANK = {"product": 0, "architecture": 1, "module": 2}          # dependencies point upward (lower rank)
REQUIRED_SECTIONS = {"product": (0, 1, 2, 3), "architecture": (0, 1, 2, 3), "module": (0, 1, 2)}
CONSTRAINTS_SECTIONS = (0, 1, 2)                                     # the constraints variant of the product template
ALLOWED = set(REQUIRED) | {"description", "sources", "locked_by", "locked_at", "deprecated_date",
                           "original_path", "dds_version", "locking", "gate"}
RESERVED_PREFIX = "product-constraint"
CONSTRAINTS_ID = "product-constraints"
ROOT_TREE = ".dds/tree.dds.md"
MANIFESTO = ".dds/meta/manifesto.dds.md"

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")
ENTRY_RE = re.compile(r"^- \[([^\]]+)\]: (.+)$")
TOMB_RE = re.compile(r"^- \[DEPRECATED -> ([^\]]+)\]: (.+)$")
BANNER_RE = re.compile(r"^> .*DEPRECATED", re.M)
SECTION_RE = re.compile(r"^## \[(\d)\]")
BARE_TAG_RE = re.compile(r"^</?[A-Za-z_]+>$")

CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".cs", ".java", ".kt", ".go", ".rs",
            ".rb", ".php", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp", ".m", ".scala", ".sql", ".vue",
            ".svelte", ".razor", ".cshtml", ".dart", ".ex", ".exs", ".erl", ".hs", ".lua", ".sh",
            ".ps1", ".pl", ".r", ".fs", ".clj", ".zig"}
SKIP_DIRS = {".git", ".dds", "node_modules", "vendor", "dist", "build", "out", "target", ".venv", "venv",
             "__pycache__", ".idea", ".vscode", "bin", "obj", "coverage"}


# ---------------------------------------------------------------- reporting

class Report:
    def __init__(self):
        self.errors, self.warns, self.infos = [], [], []

    def error(self, where, msg):
        self.errors.append((where, msg))

    def warn(self, where, msg):
        self.warns.append((where, msg))

    def info(self, where, msg):
        self.infos.append((where, msg))

    def dump(self):
        for level, items in (("ERROR", self.errors), ("WARN", self.warns), ("INFO", self.infos)):
            for where, msg in sorted(items):
                print("%s: %s: %s" % (level, where, msg))


def die(msg, code=2):
    print("dds: " + msg, file=sys.stderr)
    sys.exit(code)


def find_root(explicit):
    if explicit:
        root = Path(explicit).resolve()
        if not (root / ".dds").is_dir():
            die("%s does not contain a .dds/ directory" % root)
        return root
    cur = Path.cwd().resolve()
    for cand in (cur, *cur.parents):
        if (cand / ".dds").is_dir():
            return cand
    die("no .dds/ directory found in %s or its parents (use --root)" % cur)


def rel(root, path):
    return Path(path).resolve().relative_to(root).as_posix()


def glob_to_regex(pattern):
    """Translate a repo-relative glob (supports **, *, ?) into a compiled regex."""
    pat = pattern.strip().replace("\\", "/")
    if pat.startswith("./"):
        pat = pat[2:]
    parts = pat.split("/")
    out = []
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if part == "**":
            out.append(".*" if last else "(?:.*/)?")
            continue
        seg = ""
        for ch in part:
            seg += "[^/]*" if ch == "*" else "[^/]" if ch == "?" else re.escape(ch)
        out.append(seg if last else seg + "/")
    return re.compile("^" + "".join(out) + "$")


# ---------------------------------------------------------------- documents

class Doc:
    def __init__(self, path, root):
        self.path = path
        self.rel = rel(root, path)
        self.fm = {}
        self.body = ""
        self.eol = "\n"
        self.fm_end = 0          # index of the closing '---' line
        self.lines = []

    @property
    def id(self):
        return self.fm.get("id")

    @property
    def status(self):
        return self.fm.get("status")

    @property
    def type(self):
        return self.fm.get("type")

    @property
    def is_archived(self):
        return self.rel.startswith(".dds/archive/")

    @property
    def is_meta(self):
        return self.rel.startswith(".dds/meta/")


def parse_frontmatter(doc, report):
    text = doc.path.read_text(encoding="utf-8-sig")
    doc.eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(doc.eol)
    doc.lines = lines
    if not lines or lines[0].strip() != "---":
        report.error(doc.rel, "missing frontmatter block (file must start with ---)")
        return False
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        report.error(doc.rel, "unterminated frontmatter block")
        return False
    doc.fm_end = end
    for ln in lines[1:end]:
        if not ln.strip():
            continue
        if ln[0] in " \t":
            report.error(doc.rel, "indented frontmatter line %r (nested maps are forbidden)" % ln.strip())
            continue
        m = KEY_RE.match(ln)
        if not m:
            report.error(doc.rel, "unparseable frontmatter line %r" % ln)
            continue
        key, val = m.group(1), m.group(2).strip()
        if key in doc.fm:
            report.error(doc.rel, "duplicate frontmatter key %s" % key)
            continue
        if val.startswith("["):
            if not val.endswith("]"):
                report.error(doc.rel, "unterminated list for %s" % key)
                doc.fm[key] = []
                continue
            items = []
            for raw in val[1:-1].split(","):
                raw = raw.strip()
                if not raw:
                    continue
                quoted = len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'"
                item = raw[1:-1] if quoted else raw
                if not quoted and item.startswith("*"):
                    report.error(doc.rel, "list item %r in %s must be quoted (a bare leading * is a YAML alias)" % (item, key))
                items.append(item)
            doc.fm[key] = items
        else:
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            doc.fm[key] = val
    doc.body = doc.eol.join(lines[end + 1:])
    return True


def load_docs(root, report):
    """Return (docs_by_id, all_docs). Files without a usable id are still validated but not indexed."""
    docs, all_docs = {}, []
    for path in sorted((root / ".dds").rglob("*.dds.md")):
        if ".locks" in path.parts:
            continue
        doc = Doc(path, root)
        all_docs.append(doc)
        if not parse_frontmatter(doc, report):
            continue
        did = doc.id
        if isinstance(did, str) and did:
            if did in docs:
                report.error(doc.rel, "duplicate id %r (also used by %s)" % (did, docs[did].rel))
            else:
                docs[did] = doc
    return docs, all_docs


# ---------------------------------------------------------------- schema checks

def body_headers_and_changelog(doc):
    """Return (max_header_depth, changelog_entries) ignoring fenced code blocks."""
    depth, entries, in_fence, in_changelog = 0, 0, False, False
    for ln in doc.body.split(doc.eol):
        s = ln.rstrip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{1,6})\s", s)
        if m:
            depth = max(depth, len(m.group(1)))
            in_changelog = s.lower().startswith("## changelog")
            continue
        if in_changelog and s.startswith("- ["):
            entries += 1
    return depth, entries


def check_content(doc, report, all_files):
    """schema.dds.md [3]: an active document has every required section non-empty and every sources glob
    matching at least one file; a draft gets warnings instead. Deprecated documents are history and are skipped."""
    fm, t = doc.fm, doc.type
    say = report.error if doc.status == "active" else report.warn
    required = CONSTRAINTS_SECTIONS if (t == "product" and str(fm.get("id", "")).startswith(RESERVED_PREFIX)) else REQUIRED_SECTIONS[t]
    sections, current, in_fence = {}, None, False
    for ln in doc.body.split(doc.eol):
        s = ln.rstrip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = SECTION_RE.match(s)
        if m:
            current = int(m.group(1))
            sections.setdefault(current, 0)
            continue
        if s.startswith("## ") or s.startswith("# "):
            current = None
            continue
        if current is not None and s.strip() and not BARE_TAG_RE.match(s.strip()):
            sections[current] += 1
    for n in required:
        if n not in sections:
            say(doc.rel, "%s document is missing section [%d] (write template)" % (doc.status, n))
        elif sections[n] == 0:
            say(doc.rel, "%s document has an empty section [%d]" % (doc.status, n))
    if t == "module" and isinstance(fm.get("sources"), list):
        for g in fm["sources"]:
            if g and not any(glob_to_regex(g).match(f) for f in all_files):
                say(doc.rel, "sources glob %r matches no file in the repository" % g)


def is_code_path(rel_path):
    """A code file by extension, outside skipped and hidden directories (the same set iter_code_files walks)."""
    parts = rel_path.split("/")
    if any(part in SKIP_DIRS or part.startswith(".") for part in parts[:-1]):
        return False
    return Path(parts[-1]).suffix.lower() in CODE_EXT


def iter_all_files(root):
    """Every file under root except skipped and hidden directories; used to resolve sources globs."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for fn in filenames:
            yield Path(dirpath, fn).relative_to(root).as_posix()


def validate_docs(docs, all_docs, root, report, gate=False):
    root_tree = docs.get("tree-root")
    all_files = None
    for doc in all_docs:
        fm = doc.fm
        if not fm and not doc.lines:
            continue
        w = doc.rel
        for k in REQUIRED:
            if k not in fm:
                report.error(w, "missing required field %s" % k)
        for k in fm:
            if k not in ALLOWED:
                report.error(w, "forbidden field %s (schema.dds.md [1])" % k)
        t, s, did = fm.get("type"), fm.get("status"), fm.get("id", "")
        if "type" in fm and t not in TYPES:
            report.error(w, "type must be one of %s, got %r" % (sorted(TYPES), t))
        if "status" in fm and s not in STATUSES:
            report.error(w, "status must be one of %s, got %r" % (sorted(STATUSES), s))
        if "id" in fm:
            if not isinstance(did, str) or not ID_RE.match(did):
                report.error(w, "id %r is not lowercase kebab-case" % (did,))
            elif t in PREFIX and not did.startswith(PREFIX[t]):
                report.error(w, "id %r must start with %r for type %s" % (did, PREFIX[t], t))
            if isinstance(did, str) and did.startswith(RESERVED_PREFIX) and t != "product":
                report.error(w, "id prefix %r is reserved for non-negotiable constraints (type: product)" % RESERVED_PREFIX)
        if "last_updated" in fm and not (isinstance(fm["last_updated"], str) and DATE_RE.match(fm["last_updated"])):
            report.error(w, "last_updated must be YYYY-MM-DD")
        deps = fm.get("dependencies", [])
        if "dependencies" in fm and not isinstance(deps, list):
            report.error(w, "dependencies must be a list like [] or [id, id]")
            deps = []
        for dep in deps:
            if dep not in docs:
                report.error(w, "dependency %r does not resolve to any document (ids, not paths)" % dep)
                continue
            if s == "active" and docs[dep].status == "deprecated":
                report.error(w, "active document depends on deprecated id %r" % dep)
            dt = docs[dep].type
            if t in TIER_RANK:
                if dt not in TIER_RANK:
                    report.error(w, "dependency %r is a %s document; tier documents depend only on tier documents" % (dep, dt))
                elif TIER_RANK[dt] > TIER_RANK[t]:
                    report.error(w, "depends on a lower tier: a %s document may not depend on %r (%s); dependencies point upward (schema.dds.md [1])" % (t, dep, dt))
            elif t == "meta" and dt != "meta":
                report.error(w, "meta documents depend only on meta documents, not %r" % dep)
        if t == "tree" and deps:
            report.error(w, "tree documents declare no dependencies")
        if t in ("product", "architecture", "module") and not fm.get("description"):
            report.warn(w, "description is missing (index trees and tooling show it)")
        if "sources" in fm:
            if t != "module":
                report.error(w, "sources is allowed on module documents only")
            elif not isinstance(fm["sources"], list) or not fm["sources"]:
                report.error(w, "sources must be a non-empty list of globs")
        if t in REQUIRED_SECTIONS and s in ("active", "draft") and not doc.is_archived:
            if all_files is None:
                all_files = list(iter_all_files(root))
            check_content(doc, report, all_files)
        has_by, has_at = "locked_by" in fm, "locked_at" in fm
        if has_by != has_at:
            report.error(w, "locked_by and locked_at must appear together")
        if has_at and not ISO_RE.match(str(fm["locked_at"])):
            report.error(w, "locked_at must be ISO-8601 UTC like 2026-09-18T09:30:00Z")
        if has_by or has_at:
            (report.error if gate else report.info)(w, "lock present (locked_by=%s); locks must never be committed" % fm.get("locked_by"))
        if s == "deprecated":
            for k in ("deprecated_date", "original_path"):
                if k not in fm:
                    report.error(w, "deprecated document is missing %s" % k)
            if "deprecated_date" in fm and not DATE_RE.match(str(fm["deprecated_date"])):
                report.error(w, "deprecated_date must be YYYY-MM-DD")
            if not doc.is_archived:
                report.error(w, "deprecated document must live under .dds/archive/")
            op = fm.get("original_path")
            if isinstance(op, str) and op and (root / op).exists():
                report.warn(w, "original_path %s still exists; the archived copy should be the only one" % op)
            if not BANNER_RE.search(doc.body):
                report.warn(w, "deprecated document lacks the '> ... DEPRECATED:' banner after the frontmatter")
        else:
            for k in ("deprecated_date", "original_path"):
                if k in fm:
                    report.error(w, "%s is allowed only when status is deprecated" % k)
            if doc.is_archived:
                report.error(w, "documents under .dds/archive/ must have status: deprecated")
        is_root_tree, is_manifesto = doc.rel == ROOT_TREE, doc.rel == MANIFESTO
        if "dds_version" in fm:
            if not (is_root_tree or is_manifesto):
                report.error(w, "dds_version belongs only to %s and %s" % (ROOT_TREE, MANIFESTO))
            elif not SEMVER_RE.match(str(fm["dds_version"])):
                report.error(w, "dds_version must be MAJOR.MINOR.PATCH")
        for k, allowed in (("locking", {"on", "off"}), ("gate", {"strict", "warn"})):
            if k in fm:
                if not is_root_tree:
                    report.error(w, "%s belongs only to %s" % (k, ROOT_TREE))
                elif fm[k] not in allowed:
                    report.error(w, "%s must be one of %s" % (k, sorted(allowed)))
        if t == "tree" and not (doc.path.name.endswith(".tree.dds.md") or doc.rel == ROOT_TREE):
            report.error(w, "type: tree documents must be named <scope>.tree.dds.md")
        if t != "tree" and doc.path.name.endswith(".tree.dds.md"):
            report.error(w, "files named *.tree.dds.md must have type: tree")
        if t == "module" and doc.path.parent.resolve() == (root / ".dds" / "modules").resolve():
            report.error(w, "module documents must live in a sub-folder of .dds/modules/ (STRICT_FOLDERIZATION)")
        depth, entries = body_headers_and_changelog(doc)
        if depth > MAX_HEADER_DEPTH:
            report.warn(w, "header depth %d exceeds the H%d convention" % (depth, MAX_HEADER_DEPTH))
        if entries > CHANGELOG_CAP:
            report.warn(w, "changelog has %d entries; trim to %d (older entries stay in git log)" % (entries, CHANGELOG_CAP))

    # dependency graph must be acyclic
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {i: WHITE for i in docs}
    for start in sorted(docs):
        if color[start] != WHITE:
            continue
        stack = [(start, iter(docs[start].fm.get("dependencies", []) if isinstance(docs[start].fm.get("dependencies"), list) else []))]
        color[start] = GRAY
        path = [start]
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                color[node] = BLACK
                stack.pop()
                path.pop()
                continue
            if nxt not in docs:
                continue
            if color[nxt] == GRAY:
                cycle = path[path.index(nxt):] + [nxt]
                report.error(docs[nxt].rel, "dependency cycle: %s" % " -> ".join(cycle))
                color[nxt] = BLACK          # report each cycle once
            elif color[nxt] == WHITE:
                color[nxt] = GRAY
                path.append(nxt)
                deps_n = docs[nxt].fm.get("dependencies", [])
                stack.append((nxt, iter(deps_n if isinstance(deps_n, list) else [])))

    # cross-document rules
    manifesto = docs.get("meta-manifesto")
    if root_tree is None:
        report.error(ROOT_TREE, "root tree is missing (id tree-root)")
    else:
        rv = root_tree.fm.get("dds_version")
        mv = manifesto.fm.get("dds_version") if manifesto else None
        if rv is None:
            report.error(ROOT_TREE, "dds_version is missing")
        if manifesto and rv != mv:
            report.error(ROOT_TREE, "dds_version %s does not match manifesto %s" % (rv, mv))
        if rv and rv != DDS_VERSION:
            report.warn(ROOT_TREE, "dds_version %s differs from this script (%s)" % (rv, DDS_VERSION))
        if root_tree.fm.get("gate") == "strict":
            c = docs.get(CONSTRAINTS_ID)
            if c is None or c.status != "active":
                report.error(ROOT_TREE, "gate: strict requires an active %s document (manifesto [1].0)" % CONSTRAINTS_ID)
    if manifesto is None:
        report.error(MANIFESTO, "manifesto is missing (id meta-manifesto)")


# ---------------------------------------------------------------- tree checks

class TreeInfo:
    def __init__(self, doc):
        self.doc = doc
        self.entries = []      # (path_rel, description)
        self.children = []     # rel paths of child trees
        self.tombstones = []   # (target_rel, reason)


def validate_trees(docs, all_docs, root, report):
    trees = {}
    indexed = Counter()
    for doc in all_docs:
        if doc.type != "tree":
            continue
        info = TreeInfo(doc)
        trees[doc.rel] = info
        w = doc.rel
        folder = doc.path.parent
        expected = "tree.dds.md" if doc.rel == ROOT_TREE else folder.name + ".tree.dds.md"
        if doc.path.name != expected:
            report.error(w, "tree file must be named %s so subtree pointers can resolve" % expected)
        h1, in_comment = 0, False
        for ln in doc.body.split(doc.eol):
            s = ln.rstrip()
            if in_comment:
                if "-->" in s:
                    in_comment = False
                continue
            if not s:
                continue
            if s.startswith("<!--"):
                in_comment = "-->" not in s
                continue
            if s.startswith("# "):
                h1 += 1
                continue
            if s.startswith("> ") and doc.status == "deprecated":
                continue    # DEPRECATED banner of an archived tree
            mt = TOMB_RE.match(s)
            if mt:
                target = mt.group(1).strip()
                tp = root / target
                if not tp.exists():
                    report.error(w, "tombstone target %s does not exist" % target)
                else:
                    tdoc = next((d for d in all_docs if d.path == tp.resolve() or d.rel == target), None)
                    if tdoc is not None and tdoc.status != "deprecated":
                        report.error(w, "tombstone target %s is not status: deprecated" % target)
                info.tombstones.append((target, mt.group(2)))
                continue
            me = ENTRY_RE.match(s)
            if not me:
                report.error(w, "invalid tree line %r (schema.dds.md [4])" % s)
                continue
            target = me.group(1).strip()
            if target.endswith("/"):
                last = target.rstrip("/").split("/")[-1]
                child = folder / target / (last + ".tree.dds.md")
                if not child.exists():
                    report.error(w, "subtree pointer %s expects %s" % (target, rel(root, child) if child.parent.exists() else target + last + ".tree.dds.md"))
                else:
                    info.children.append(rel(root, child))
            else:
                fp = folder / target
                if not fp.exists():
                    report.error(w, "entry %s does not exist" % target)
                    continue
                if fp.resolve().parent != folder.resolve():
                    report.error(w, "entry %s is outside this tree's folder" % target)
                    continue
                r = rel(root, fp)
                indexed[r] += 1
                info.entries.append((r, me.group(2)))
        if h1 != 1:
            report.error(w, "tree must contain exactly one H1, found %d" % h1)
    # every governed document indexed exactly once
    for doc in all_docs:
        if doc.type in ("tree", "meta") or doc.is_archived or doc.is_meta or not doc.fm:
            continue
        n = indexed.get(doc.rel, 0)
        if n != 1:
            report.error(doc.rel, "indexed %d time(s) by its folder tree; must be exactly 1" % n)
    # reachability: exactly one chain from the root
    if ROOT_TREE in trees:
        seen = Counter()
        queue = deque([ROOT_TREE])
        while queue:
            t = queue.popleft()
            seen[t] += 1
            if seen[t] > 1:
                report.error(t, "reachable from the root through more than one pointer chain")
                continue
            queue.extend(trees[t].children if t in trees else [])
        for t in trees:
            if t not in seen and not trees[t].doc.is_archived:
                report.error(t, "tree is unreachable from %s (orphaned knowledge)" % ROOT_TREE)
    return trees


# ---------------------------------------------------------------- adoption reports

def module_globs(docs):
    out = []
    for d in docs.values():
        if d.type == "module" and isinstance(d.fm.get("sources"), list):
            out.append((d, [glob_to_regex(g) for g in d.fm["sources"] if g]))
    return out


def iter_code_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for fn in filenames:
            if Path(fn).suffix.lower() in CODE_EXT:
                yield Path(dirpath, fn).relative_to(root).as_posix()


def check_coverage(root, docs, report):
    """Adoption report: which code files no module document governs. Works before the first module document exists."""
    globs = module_globs(docs)
    files = list(iter_code_files(root))
    if not files:
        report.info("coverage", "no code files found under %s" % root)
        return
    if not globs:
        report.info("coverage", "no module document declares sources: yet; every code file below is ungoverned (adopt.dds.md [2])")
    covered, uncovered_dirs = 0, Counter()
    for f in files:
        if any(rx.match(f) for _, rxs in globs for rx in rxs):
            covered += 1
        else:
            parts = f.split("/")
            uncovered_dirs["/".join(parts[:2]) if len(parts) > 2 else parts[0]] += 1
    pct = 100.0 * covered / len(files)
    report.info("coverage", "%d/%d code files covered by module sources (%.0f%%)" % (covered, len(files), pct))
    for d, n in uncovered_dirs.most_common(25):
        report.warn("coverage", "%s: %d code file(s) not governed by any module document" % (d, n))


def git_changed_paths(root):
    """Changed paths relative to root (not to the git toplevel), or None when git is unavailable."""
    try:
        out = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "-z"],
                             capture_output=True, check=True).stdout.decode("utf-8", "replace")
        prefix = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-prefix"],
                                capture_output=True, check=True).stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    changed, recs, i = set(), out.split("\0"), 0
    while i < len(recs):
        r = recs[i]
        i += 1
        if len(r) < 4:
            continue
        code, path = r[:2], r[3:]
        paths = [path]
        if code[0] in "RC" and i < len(recs):   # rename/copy: next record is the original path
            paths.append(recs[i])
            i += 1
        for pth in paths:
            if pth.startswith(prefix):
                changed.add(pth[len(prefix):])
    return changed


def git_staged_paths(root):
    """Paths staged in the git index, relative to root; None when git or the index is unavailable."""
    try:
        out = subprocess.run(["git", "-C", str(root), "diff", "--cached", "--name-only", "-z"],
                             capture_output=True, check=True).stdout.decode("utf-8", "replace")
        prefix = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-prefix"],
                                capture_output=True, check=True).stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return {p[len(prefix):] for p in out.split("\0") if p and p.startswith(prefix)}


def check_staged(root, docs, report, gate):
    """manifesto [1].3: staged code under an active document's sources requires that document to be staged too.
    Error in gate mode (agents, CI-less commits), warning otherwise. There is no bypass at the gate; humans
    under gate: warn are let through by their hook, and the DDS-No-Doc trailer is a CI-era check, not a switch."""
    staged = git_staged_paths(root)
    if staged is None:
        report.info("staged", "git index unavailable; staged check skipped")
        return
    if not staged:
        report.info("staged", "nothing is staged")
        return
    globs = module_globs(docs)
    for d, rxs in globs:
        if d.status != "active":
            continue
        hits = sorted(p for p in staged if any(rx.match(p) for rx in rxs))
        if hits and d.rel not in staged:
            (report.error if gate else report.warn)(
                d.rel, "staged code under sources (%s%s) without this document; stage the governing document in the same commit (manifesto [1].3)"
                % (", ".join(hits[:3]), "..." if len(hits) > 3 else ""))
    # adopt.dds.md [4]: code that no module document governs is not changed before a draft document exists.
    # Skipped when the repository has no module documents at all (nothing to govern yet, e.g. the DDS repo itself).
    if globs:
        governed = [rx for d, rxs in globs if d.status != "deprecated" for rx in rxs]
        for p in sorted(staged):
            if not is_code_path(p):
                continue
            if not any(rx.match(p) for rx in governed):
                (report.error if gate else report.warn)(
                    p, "staged code that no module document governs; create a draft document first (adopt.dds.md [2].3)")


def check_sync(root, docs, report):
    changed = git_changed_paths(root)
    if changed is None:
        report.info("sync", "git status unavailable; drift detection skipped")
        return
    globs = module_globs(docs)
    if not globs:
        report.info("sync", "no module document declares sources:; nothing to compare")
        return
    for d, rxs in globs:
        hits = sorted(p for p in changed if any(rx.match(p) for rx in rxs))
        if hits and d.rel not in changed:
            report.warn(d.rel, "sources changed (%s%s) but this document was not touched; drift?"
                        % (", ".join(hits[:3]), "..." if len(hits) > 3 else ""))


# ---------------------------------------------------------------- commands

def cmd_check(args):
    root = find_root(args.root)
    report = Report()
    docs, all_docs = load_docs(root, report)
    validate_docs(docs, all_docs, root, report, gate=args.gate)
    validate_trees(docs, all_docs, root, report)
    if args.staged:
        check_staged(root, docs, report, args.gate)
    if args.coverage:
        check_coverage(root, docs, report)
    if args.sync:
        check_sync(root, docs, report)
    report.dump()
    trees = sum(1 for d in all_docs if d.type == "tree")
    print("documents: %d  trees: %d  dds_version: %s  script: %s" % (
        len(all_docs), trees, (docs.get("tree-root").fm.get("dds_version") if docs.get("tree-root") else "?"), DDS_VERSION))
    if report.errors:
        print("RESULT: FAIL (%d errors, %d warnings)%s" % (len(report.errors), len(report.warns), " [gate]" if args.gate else ""))
        return 1
    print("RESULT: PASS (%d warnings)%s" % (len(report.warns), " [gate]" if args.gate else ""))
    return 0


def cmd_impact(args):
    root = find_root(args.root)
    report = Report()
    docs, _ = load_docs(root, report)
    target = docs.get(args.id)
    if target is None:
        die("unknown id %r" % args.id)
    live = {i: d for i, d in docs.items() if d.status != "deprecated"}

    def line(d, extra=""):
        return "%s\t%s\t%s\t%s%s" % (d.id, d.status, d.type, d.rel, extra)

    if args.up:
        print("# direct dependencies of %s (what it obeys)" % args.id)
        for dep in target.fm.get("dependencies", []):
            d = docs.get(dep)
            print(line(d) if d else "%s\tMISSING\t-\t-" % dep)
        return 0
    dependents = lambda i: sorted((d for d in live.values() if i in d.fm.get("dependencies", [])), key=lambda d: d.id)
    if args.down:
        print("# cascade set of %s: transitive dependents (depth\tid\tstatus\ttype\tpath)" % args.id)
        seen, queue = set(), deque((d, 1) for d in dependents(args.id))
        while queue:
            d, depth = queue.popleft()
            if d.id in seen:
                continue
            seen.add(d.id)
            print("%d\t%s" % (depth, line(d)))
            queue.extend((c, depth + 1) for c in dependents(d.id))
        if not seen:
            print("# (none)")
        return 0
    print("# direct dependents of %s (id\tstatus\ttype\tpath)" % args.id)
    rows = dependents(args.id)
    for d in rows:
        print(line(d))
    if not rows:
        print("# (none)")
    return 0


def rewrite_frontmatter(doc, updates, remove):
    lines = doc.lines[:]
    head = lines[1:doc.fm_end]
    kept = [ln for ln in head if not (KEY_RE.match(ln) and KEY_RE.match(ln).group(1) in set(remove) | set(updates))]
    for k, v in updates.items():
        kept.append("%s: %s" % (k, v))
    new = [lines[0]] + kept + lines[doc.fm_end:]
    doc.path.write_text(doc.eol.join(new), encoding="utf-8")


def load_single(root, file_arg, report):
    path = Path(file_arg)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.exists():
        die("%s does not exist" % file_arg)
    try:
        doc = Doc(path, root)
    except ValueError:
        die("%s is outside the repository root %s" % (file_arg, root))
    if not parse_frontmatter(doc, report) or not doc.id:
        report.dump()
        die("%s has no valid frontmatter/id" % doc.rel, 1)
    return doc


def locking_enabled(root):
    report = Report()
    tree = Doc(root / ".dds" / "tree.dds.md", root)
    if not tree.path.exists() or not parse_frontmatter(tree, report):
        return False
    return tree.fm.get("locking") == "on"


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def cmd_lock(args):
    root = find_root(args.root)
    if not locking_enabled(root):
        print("STATUS: LOCKING_OFF (%s has no locking: on); nothing to do" % ROOT_TREE)
        return 0
    doc = load_single(root, args.file, Report())
    lockdir = root / ".dds" / ".locks"
    lockdir.mkdir(exist_ok=True)
    lockfile = lockdir / (doc.id + ".lock")
    stamp = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
    status = "LOCKED"
    try:
        fd = os.open(str(lockfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("%s\n%s\n" % (args.by, stamp))
    except FileExistsError:
        try:
            owner, at = (lockfile.read_text(encoding="utf-8").split("\n") + ["", ""])[:2]
            age_min = (now_utc() - datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 60
        except (ValueError, OSError):
            owner, age_min = "unknown", LOCK_TIMEOUT_MIN + 1
        if owner == args.by:
            status = "LOCK_REFRESHED"
        elif age_min <= LOCK_TIMEOUT_MIN:
            print("STATUS: LOCKED_BY %s (%d min); retry later" % (owner, int(age_min)))
            return 1
        else:
            status = "LOCK_TAKEN_OVER from %s (%d min stale)" % (owner, int(age_min))
        # release the old sidecar and re-acquire atomically; a rival who wins the race is reported, not overwritten
        try:
            lockfile.unlink()
        except FileNotFoundError:
            pass
        try:
            fd = os.open(str(lockfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write("%s\n%s\n" % (args.by, stamp))
        except FileExistsError:
            rival = (lockfile.read_text(encoding="utf-8").split("\n") + [""])[0]
            print("STATUS: LOCKED_BY %s (acquired while taking over); retry later" % rival)
            return 1
    rewrite_frontmatter(doc, {"locked_by": args.by, "locked_at": stamp}, set())
    print("STATUS: %s %s by %s at %s" % (status, doc.id, args.by, stamp))
    return 0


def cmd_unlock(args):
    root = find_root(args.root)
    doc = load_single(root, args.file, Report())
    lockfile = root / ".dds" / ".locks" / (doc.id + ".lock")
    owner = None
    if lockfile.exists():
        owner = lockfile.read_text(encoding="utf-8").split("\n")[0]
        lockfile.unlink()
    rewrite_frontmatter(doc, {}, {"locked_by", "locked_at"})
    print("STATUS: UNLOCKED %s%s" % (doc.id, " (was held by %s)" % owner if owner else ""))
    return 0


def cmd_tree(args):
    root = find_root(args.root)
    report = Report()
    docs, all_docs = load_docs(root, report)
    trees = validate_trees(docs, all_docs, root, report)

    def render(t, indent):
        info = trees.get(t)
        if info is None:
            return
        print("%s%s" % ("  " * indent, t))
        for r, desc in info.entries:
            d = next((x for x in all_docs if x.rel == r), None)
            print("%s  - %s [%s] %s" % ("  " * indent, r.rsplit("/", 1)[-1], d.status if d else "?", desc))
        for target, reason in info.tombstones:
            print("%s  - DEPRECATED -> %s : %s" % ("  " * indent, target, reason))
        for c in info.children:
            render(c, indent + 1)

    render(ROOT_TREE, 0)
    tree_problems = [e for e in report.errors if e[0] in trees or "indexed" in e[1]]
    print()
    for where, msg in sorted(tree_problems):
        print("ERROR: %s: %s" % (where, msg))
    print("RESULT: %s (%d tree problems)" % ("FAIL" if tree_problems else "PASS", len(tree_problems)))
    return 1 if tree_problems else 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):      # Windows consoles default to cp1252; documents are UTF-8
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="dds.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", help="directory containing .dds/ (default: nearest ancestor of cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="validate the .dds/ tree")
    c.add_argument("--gate", action="store_true", help="commit-gate mode: present locks and staged-code violations are errors")
    c.add_argument("--staged", action="store_true", help="staged code under an active document's sources requires that document to be staged too")
    c.add_argument("--coverage", action="store_true", help="report code files not governed by module sources:")
    c.add_argument("--sync", action="store_true", help="warn when sources changed but the document did not")
    c.set_defaults(fn=cmd_check)
    i = sub.add_parser("impact", help="dependency graph queries")
    i.add_argument("id")
    g = i.add_mutually_exclusive_group()
    g.add_argument("--up", action="store_true", help="the document's own dependencies")
    g.add_argument("--down", action="store_true", help="transitive dependents (cascade set)")
    i.set_defaults(fn=cmd_impact)
    l = sub.add_parser("lock", help="acquire a lock on a document")
    l.add_argument("file")
    l.add_argument("--by", required=True, metavar="EXECUTOR_ID")
    l.set_defaults(fn=cmd_lock)
    u = sub.add_parser("unlock", help="release a lock")
    u.add_argument("file")
    u.set_defaults(fn=cmd_unlock)
    t = sub.add_parser("tree", help="render index trees and report index problems")
    t.set_defaults(fn=cmd_tree)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
