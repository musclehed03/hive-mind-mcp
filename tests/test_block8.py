"""Block 8 gate tests: demo + polish, no new features.

Polish SOP: lazy loading, no dead references, fetching never degrades
the experience, no polling, pinned dependencies, no leftover markers
in shipped code, and every local reference in the docs resolves.
"""

import ast
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _walk(exts, base=None, skip_dirs=("__pycache__", ".venv", ".git")):
    root0 = os.path.join(REPO, base) if base else REPO
    for root, dirs, files in os.walk(root0):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            if any(name.endswith(e) for e in exts):
                yield os.path.join(root, name)


def test_no_todo_or_fixme_in_shipped_code():
    # Shipped code only: app/ + gui/. Tests and docs may mention the
    # word (the license item is tracked in the submission checklist).
    for base in ("app", "gui"):
        for path in _walk((".py", ".js", ".css", ".html"), base=base):
            with open(path, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    assert "TODO" not in line and "FIXME" not in line, f"{path}:{i}"


def test_no_polling_or_timers_in_gui():
    # Revised for fast custom tooltips (standing SOP, ~500ms) and
    # for the Block 16 copy buttons: the ONLY timers allowed in the
    # GUI are two one-shot setTimeout calls in app.js — the tooltip
    # delay (always paired with clearTimeout) and the "Copied"
    # button-text revert. Neither is polling. setInterval stays
    # banned everywhere, and no other setTimeout may appear.
    # Widening this beyond those two one-shot delays would weaken
    # the guard.
    for name in ("app.js", "clipper.html"):
        with open(os.path.join(REPO, "gui", name), encoding="utf-8") as f:
            js = f.read()
        assert "setInterval" not in js, name
        if name == "app.js":
            assert js.count("setTimeout") == 2, "tooltip delay + copy revert only"
            assert "TOOLTIP_DELAY_MS = 500" in js
            assert "clearTimeout" in js
            assert "Copied" in js
        else:
            assert "setTimeout" not in js, name
    with open(os.path.join(REPO, "gui", "app.js"), encoding="utf-8") as f:
        assert "requestAnimationFrame" in f.read()


def test_no_network_imports_anywhere_in_app():
    # Revised for the live adapters (parent task, Blocks 4-5 live
    # gates) and for the Block 16 Integrations status probe: stdlib
    # urllib imports are allowed ONLY in app/live_meta.py and
    # app/live_supabase.py, the env-gated live clients that are
    # never used by default, plus app/integrations.py, whose only
    # network use is a short-timeout localhost health check of the
    # SSE server (127.0.0.1:8765, best-effort, failure = "not
    # running"). Every other app/ file is still banned from all
    # network imports. Widening this exemption beyond these three
    # files would weaken the guard.
    banned = ("socket", "urllib", "http.client", "requests", "httpx", "websocket")
    allowed = {"live_meta.py", "live_supabase.py", "integrations.py"}
    for path in _walk((".py",), base="app"):
        if os.path.basename(path) in allowed:
            banned_here = ("socket", "http.client", "requests", "httpx", "websocket")
        else:
            banned_here = banned
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in banned_here, path
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in banned_here, path


def test_fake_clients_are_labelled_fake():
    with open(os.path.join(REPO, "app", "fake_meta.py"), encoding="utf-8") as f:
        src = f.read()
    assert "FAKE_MODEL" in src
    assert "fake" in src.lower()
    with open(os.path.join(REPO, "app", "fake_supabase.py"), encoding="utf-8") as f:
        assert "Fake" in f.read()


def test_requirements_pinned():
    with open(os.path.join(REPO, "requirements.txt"), encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    assert lines, "requirements.txt is empty"
    for line in lines:
        assert "==" in line, line


def test_demo_script_covers_all_four_beats():
    with open(os.path.join(REPO, "docs", "DEMO_SCRIPT.md"), encoding="utf-8") as f:
        script = f.read()
    for beat in ("Bedroom Epiphany", "Cross-Hatch", "Money Shot", "Micro-Bot"):
        assert beat in script
    assert "3:00" in script or "3-minute" in script
    assert "hivemind_capture_idea" in script
    assert "hivemind_snapshot_backup" in script


def test_docs_local_references_resolve():
    for doc in ("README.md", "docs/DEMO_SCRIPT.md", "docs/SUBMISSION_CHECKLIST.md"):
        with open(os.path.join(REPO, doc), encoding="utf-8") as f:
            text = f.read()
        for match in re.findall(r"`([a-zA-Z0-9_./-]+\.(?:py|md|js|html|css|txt|yml|example))`", text):
            if match.startswith("http"):
                continue
            if match.startswith("src/theme/"):
                continue  # canonical palette tokens live in the website repo
            assert os.path.exists(os.path.join(REPO, match)), f"{doc}: {match}"


def test_gui_files_referenced_by_gui_server_exist():
    gui_dir = os.path.join(REPO, "gui")
    for name in ("index.html", "styles.css", "app.js", "settings-data.js",
                 "logo.svg", "clipper.html", "bookmarklet.js"):
        assert os.path.exists(os.path.join(gui_dir, name)), name


def test_all_python_files_compile():
    for path in _walk((".py",)):
        with open(path, encoding="utf-8") as f:
            compile(f.read(), path, "exec")
