#!/usr/bin/env python3
"""
check-docs-drift.py

Cross-checks the doc system — feature files, backlog.md, requirements-index.md,
product-requirements.md, tasks.md, decisions.md — for drift: places where the
same fact is recorded in more than one file and the records disagree.
The doc-system sibling of check-schema-drift.py. Exits 0 if aligned, 1 if drift.

Usage:
    python3 scripts/check-docs-drift.py      # stdlib only — no venv needed

What it checks (errors — same fact, two records, disagreement):
  - Feature file status vs backlog.md row status
  - Feature file <-> backlog coverage (every file has a row in Priority
    Queue/Blocked/Deferred; every row has a file)
  - Feature `req:` vs backlog Req column; feature <-> requirements-index
    Features column (both directions); a feature citing a REQ with no index
    row (features exist only after breakdown creates the row); an index row
    for a REQ absent from product-requirements.md
  - `depends-on`: targets exist; feature file vs backlog Depends On column
  - Approval gates: status `ready`+ requires all three approval flags `yes`
  - Metadata blocks: required fields present, values valid, id matches filename
  - Blocked/Deferred: feature status <-> backlog section membership; `blocked`
    requires a non-none blocked-by
  - Up Next pins: pinned features exist and are not `done`
  - Task IDs unique across Open + Closed; valid type/status; linked features exist
  - requirements-index: valid statuses; Evolves/Evolved By bidirectional;
    status roll-up vs linked feature statuses

What it reports as warnings (printed, no exit-code impact):
  - decisions.md entries missing template fields, ID gaps, out-of-order dates
    (append-only file — old entries can't be retro-fixed)
  - `## Migration File` sections of done features naming files absent from
    api/alembic/versions/
  - Deferred backlog rows with no revisit trigger; unparseable table rows

Informational output (by design, never an error):
  - REQs present in product-requirements.md with no requirements-index row.
    That is the designed "awaiting breakdown" signal, not drift — it is
    printed on every run so the state is impossible to overlook.

What it does NOT check:
  - Prose and spec quality; whether approvals actually happened (only that
    recorded state is self-consistent); anything schema (check-schema-drift.py
    owns that).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "devdocs"   # docs/ 是 GitHub Pages 发布目录，流程文档在 devdocs/
FEATURES_DIR = DOCS / "features"
BACKLOG_MD = DOCS / "backlog.md"
INDEX_MD = DOCS / "requirements-index.md"
PRD_MD = DOCS / "product-requirements.md"
TASKS_MD = DOCS / "tasks.md"
DECISIONS_MD = DOCS / "decisions.md"

FEATURE_STATUSES = {"backlog", "drafted", "ready", "in-progress", "review", "done", "blocked", "deferred"}
APPROVAL_GATED = {"ready", "in-progress", "review", "done"}
REQ_STATUSES = {"ready", "in-progress", "done", "deferred"}
TASK_TYPES = {"bug", "debt", "chore"}
OPEN_TASK_STATUSES = {"open", "in-progress"}
META_FIELDS = [
    "id", "status", "depends-on", "blocked-by", "req",
    "complex-ui", "schema-approved", "api-approved", "ux-approved",
]
YES_NO = {"yes", "no"}
APPROVAL_FLAGS = ("schema-approved", "api-approved", "ux-approved")

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


# ---------------------------------------------------------------------------
# Parsing helpers

def clean_cell(s: str) -> str:
    return s.strip().strip("`").strip()


def split_ids(cell: str) -> list[str]:
    """Turn a 'none' / '—' / 'F-001, F-002' cell into a list of IDs."""
    cell = clean_cell(cell)
    if cell.lower() in {"none", "", "—", "-"}:
        return []
    return [clean_cell(p) for p in cell.split(",") if clean_cell(p)]


def table_rows(lines: list[str]) -> list[list[str]]:
    """Data rows (cell lists) from markdown-table lines; skips header + separator."""
    rows: list[list[str]] = []
    seen_header = False
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            continue
        if re.match(r"^\|[\s\-|]+$", s):  # |---|---| separator
            continue
        cells = s.split("|")
        if cells and cells[0].strip() == "":
            cells = cells[1:]
        if cells and cells[-1].strip() == "":
            cells = cells[:-1]
        cells = [c.strip() for c in cells]
        if not seen_header:
            seen_header = True  # first pipe row is the header
            continue
        rows.append(cells)
    return rows


def sections(text: str) -> dict[str, list[str]]:
    """Split markdown into {level-2 heading: body lines}."""
    out: dict[str, list[str]] = {}
    cur: str | None = None
    for ln in text.splitlines():
        m = re.match(r"^##\s+(.*)$", ln)
        if m:
            cur = m.group(1).strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(ln)
    return out


def section_body(text: str, heading: str) -> str | None:
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else None


def parse_feature(path: Path) -> tuple[dict[str, str] | None, str]:
    text = path.read_text()
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        err(f"{path.name}: missing metadata block")
        return None, text
    meta: dict[str, str] = {}
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        m = re.match(r"^([a-z-]+):\s*(.*)$", ln.strip())
        if m:
            meta[m.group(1)] = m.group(2).strip()
    return meta, text


# ---------------------------------------------------------------------------
# Checks

def load_features() -> dict[str, dict]:
    features: dict[str, dict] = {}
    for path in sorted(FEATURES_DIR.glob("F-*.md")):
        m = re.match(r"(F-\d{3})", path.name)
        if not m:
            warn(f"{path.name}: filename doesn't start with F-NNN")
            continue
        fid = m.group(1)
        meta, text = parse_feature(path)
        if meta is None:
            continue

        missing = [f for f in META_FIELDS if f not in meta]
        if missing:
            err(f"{path.name}: metadata missing field(s): {', '.join(missing)}")
        if meta.get("id") and meta["id"] != fid:
            err(f"{path.name}: metadata id `{meta['id']}` doesn't match filename `{fid}`")
        status = meta.get("status", "")
        if status and status not in FEATURE_STATUSES:
            err(f"{fid}: invalid status `{status}`")
        for flag in ("complex-ui", *APPROVAL_FLAGS):
            v = meta.get(flag, "")
            if v and v not in YES_NO:
                err(f"{fid}: invalid {flag} value `{v}`")

        features[fid] = {"meta": meta, "text": text, "name": path.name}
    return features


def check_feature_rules(features: dict[str, dict]) -> None:
    for fid, f in features.items():
        meta = f["meta"]
        status = meta.get("status", "")
        if status in APPROVAL_GATED:
            not_yes = [fl for fl in APPROVAL_FLAGS if meta.get(fl) != "yes"]
            if not_yes:
                err(f"{fid}: status `{status}` but {', '.join(not_yes)} not `yes`")
        if status == "blocked" and clean_cell(meta.get("blocked-by", "")).lower() in {"none", ""}:
            err(f"{fid}: status `blocked` but blocked-by is `none`")
        for dep in split_ids(meta.get("depends-on", "")):
            if dep not in features:
                err(f"{fid}: depends-on `{dep}` — no such feature file")


def check_backlog(features: dict[str, dict]) -> None:
    bsec = sections(BACKLOG_MD.read_text())

    queue: dict[str, dict] = {}
    for row in table_rows(bsec.get("Priority Queue", [])):
        if len(row) != 5:
            warn(f"backlog.md Priority Queue: unparseable row: {' | '.join(row)[:80]}")
            continue
        queue[clean_cell(row[0])] = {
            "status": clean_cell(row[2]),
            "deps": split_ids(row[3]),
            "reqs": split_ids(row[4]),
        }

    blocked_ids = {clean_cell(r[0]) for r in table_rows(bsec.get("Blocked", [])) if r}
    deferred_rows = table_rows(bsec.get("Deferred", []))
    deferred_ids = {clean_cell(r[0]) for r in deferred_rows if r}
    for r in deferred_rows:
        if len(r) >= 4 and not clean_cell(r[3]):
            warn(f"backlog.md Deferred: {clean_cell(r[0])} has no revisit trigger")

    # Coverage — a feature must appear somewhere in backlog.md, and vice versa
    listed = set(queue) | blocked_ids | deferred_ids
    for fid in features:
        if fid not in listed:
            err(f"{fid}: feature file exists but no row anywhere in backlog.md")
    for bid in listed:
        if bid not in features:
            err(f"backlog.md: `{bid}` listed but no feature file exists")

    # Same-fact comparisons for queue rows
    for fid, row in queue.items():
        f = features.get(fid)
        if not f:
            continue
        meta = f["meta"]
        if meta.get("status", "") != row["status"]:
            err(f"{fid}: status drift — feature file `{meta.get('status', '')}`, backlog.md `{row['status']}`")
        file_deps = set(split_ids(meta.get("depends-on", "")))
        if file_deps != set(row["deps"]):
            err(f"{fid}: depends-on drift — feature file {sorted(file_deps) or ['none']}, "
                f"backlog.md {sorted(row['deps']) or ['none']}")
        file_reqs = set(split_ids(meta.get("req", "")))
        if file_reqs != set(row["reqs"]):
            err(f"{fid}: req drift — feature file {sorted(file_reqs)}, backlog.md Req column {sorted(row['reqs'])}")

    # Blocked/Deferred membership must match file status, both directions
    file_blocked = {fid for fid, f in features.items() if f["meta"].get("status") == "blocked"}
    file_deferred = {fid for fid, f in features.items() if f["meta"].get("status") == "deferred"}
    for fid in sorted(file_blocked - blocked_ids):
        err(f"{fid}: status `blocked` but not listed in backlog.md ## Blocked")
    for fid in sorted(blocked_ids - file_blocked):
        err(f"backlog.md ## Blocked lists {fid} but its file status is not `blocked`")
    for fid in sorted(file_deferred - deferred_ids):
        err(f"{fid}: status `deferred` but not listed in backlog.md ## Deferred")
    for fid in sorted(deferred_ids - file_deferred):
        err(f"backlog.md ## Deferred lists {fid} but its file status is not `deferred`")

    # Up Next pins
    for ln in bsec.get("Up Next", []):
        if "<!--" in ln:
            continue
        for pid in re.findall(r"F-\d{3}", ln):
            if pid not in features:
                err(f"backlog.md ## Up Next pins `{pid}` — no such feature")
            elif features[pid]["meta"].get("status") == "done":
                err(f"backlog.md ## Up Next pins `{pid}` but it is `done` — protocol says remove the pin")


def check_index(features: dict[str, dict]) -> tuple[dict[str, dict], set[str]]:
    index: dict[str, dict] = {}
    for row in table_rows(INDEX_MD.read_text().splitlines()):
        if len(row) != 5:
            warn(f"requirements-index.md: unparseable row: {' | '.join(row)[:80]}")
            continue
        index[clean_cell(row[0])] = {
            "status": clean_cell(row[1]),
            "evolves": split_ids(row[2]),
            "evolved_by": split_ids(row[3]),
            "features": split_ids(row[4]),
        }

    prd_reqs = set(re.findall(r"^## (REQ-\d{3})\b", PRD_MD.read_text(), re.M))

    for rid, r in index.items():
        if rid not in prd_reqs:
            err(f"requirements-index.md: {rid} has an index row but no spec in product-requirements.md")
        if r["status"] not in REQ_STATUSES:
            err(f"requirements-index.md: {rid} invalid status `{r['status']}`")

        for other in r["evolves"]:
            if other not in index:
                err(f"requirements-index.md: {rid} evolves {other}, but {other} has no index row")
            elif rid not in index[other]["evolved_by"]:
                err(f"requirements-index.md: {rid} evolves {other}, but {other}'s Evolved By doesn't list {rid}")
        for other in r["evolved_by"]:
            if other not in index:
                err(f"requirements-index.md: {rid} evolved by {other}, but {other} has no index row")
            elif rid not in index[other]["evolves"]:
                err(f"requirements-index.md: {rid} evolved by {other}, but {other}'s Evolves doesn't list {rid}")

        for fid in r["features"]:
            if fid not in features:
                err(f"requirements-index.md: {rid} links {fid} — no such feature file")
            elif rid not in split_ids(features[fid]["meta"].get("req", "")):
                err(f"requirements-index.md: {rid} links {fid}, but {fid}'s req: doesn't cite {rid}")

        # Status roll-up vs linked features (deferred REQs are a human choice — skip)
        fstatuses = [features[f]["meta"].get("status") for f in r["features"] if f in features]
        if r["status"] == "done" and any(s != "done" for s in fstatuses):
            not_done = [f for f in r["features"] if f in features and features[f]["meta"].get("status") != "done"]
            err(f"requirements-index.md: {rid} is `done` but {', '.join(not_done)} not `done`")
        if r["status"] not in {"done", "deferred"} and fstatuses and all(s == "done" for s in fstatuses):
            err(f"requirements-index.md: {rid} is `{r['status']}` but all its features are `done` — roll up to done")

    # Feature -> index direction
    for fid, f in sorted(features.items()):
        for rid in split_ids(f["meta"].get("req", "")):
            if rid not in prd_reqs:
                err(f"{fid}: req cites {rid}, which is not in product-requirements.md")
            if rid not in index:
                err(f"{fid}: req cites {rid}, which has no requirements-index row "
                    f"(features exist only after breakdown creates the row)")
            elif fid not in index[rid]["features"]:
                err(f"{fid}: req cites {rid}, but the {rid} index row doesn't link {fid}")

    return index, prd_reqs


def check_tasks(features: dict[str, dict]) -> dict[str, str]:
    tsec = sections(TASKS_MD.read_text())
    seen: dict[str, str] = {}

    for section, min_cells in (("Open", 5), ("Closed", 4)):
        for row in table_rows(tsec.get(section, [])):
            if len(row) < min_cells:
                warn(f"tasks.md {section}: unparseable row: {' | '.join(row)[:60]}")
                continue
            tid, ttype = clean_cell(row[0]), clean_cell(row[1])
            if tid in seen:
                where = f"twice in {section}" if seen[tid] == section else f"in {seen[tid]} and {section}"
                err(f"tasks.md: duplicate task ID {tid} ({where})")
            seen[tid] = section
            if ttype not in TASK_TYPES:
                err(f"tasks.md {section}: {tid} invalid type `{ttype}`")
            if section == "Open":
                status = clean_cell(row[-1])
                if status not in OPEN_TASK_STATUSES:
                    err(f"tasks.md Open: {tid} status `{status}` — done tasks move to Closed")
                for lf in split_ids(row[-2]):
                    if lf.startswith("F-") and lf not in features:
                        err(f"tasks.md Open: {tid} links `{lf}` — no such feature")
    return seen


def check_decisions() -> set[str]:
    text = DECISIONS_MD.read_text()
    matches = list(re.finditer(r"^### (D-\d{3}) — .+ \((\d{4}-\d{2}-\d{2})\)\s*$", text, re.M))
    seen: set[str] = set()
    prev_date = ""
    for i, m in enumerate(matches):
        did, date = m.group(1), m.group(2)
        if did in seen:
            err(f"decisions.md: duplicate entry ID {did}")
        seen.add(did)
        if date < prev_date:
            warn(f"decisions.md: {did} ({date}) is out of chronological order")
        prev_date = date

        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():body_end]
        missing = [name for name, pat in
                   (("Context", r"\*\*Context\b"), ("Decision", r"\*\*Decision\b"),
                    ("Rationale", r"\*\*Rationale\b"), ("Consequences", r"\*\*Consequences\b"))
                   if not re.search(pat, body)]
        if missing:
            warn(f"decisions.md: {did} missing template field(s): {', '.join(missing)}")

    nums = sorted(int(d.split("-")[1]) for d in seen)
    gaps = [n for n in range(nums[0], nums[-1] + 1) if n not in set(nums)] if nums else []
    if gaps:
        warn(f"decisions.md: gap(s) in D-numbering: {', '.join(f'D-{n:03d}' for n in gaps)}")
    return seen


def check_migration_references(features: dict[str, dict]) -> None:
    # trip-compare 没有数据库迁移；数据模型的漂移检查由 JSON 往返测试承担
    # （tests/test_extraction.py 的 test_json_roundtrip_keeps_excluded）。
    return


# ---------------------------------------------------------------------------

def main() -> int:
    for p in (FEATURES_DIR, BACKLOG_MD, INDEX_MD, PRD_MD, TASKS_MD, DECISIONS_MD):
        if not p.exists():
            print(f"ERROR: {p} not found.", file=sys.stderr)
            return 2

    features = load_features()
    check_feature_rules(features)
    check_backlog(features)
    index, prd_reqs = check_index(features)
    tasks = check_tasks(features)
    decisions = check_decisions()
    check_migration_references(features)

    # Informational — the designed awaiting-breakdown signal, surfaced every run
    awaiting = sorted(prd_reqs - set(index))
    if awaiting:
        print(f"Awaiting breakdown ({len(awaiting)}) — in product-requirements.md with no index row "
              f"(by design, not drift): {', '.join(awaiting)}")
    else:
        print("Awaiting breakdown: none — every PRD requirement has an index row.")
    sys.stdout.flush()

    if warnings:
        print(f"\nWarnings ({len(warnings)}, non-blocking):", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)

    if errors:
        print(f"\nDocs drift detected ({len(errors)} issue{'s' if len(errors) != 1 else ''}):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("\nReconcile the disagreeing records — CLAUDE.md's File Map says which file owns each fact.",
              file=sys.stderr)
        return 1

    print(f"OK — {len(features)} features, {len(index)} indexed REQs, {len(tasks)} tasks, "
          f"{len(decisions)} decisions aligned across docs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
