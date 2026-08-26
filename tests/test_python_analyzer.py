from pathlib import Path

from magi.analyzer import python_analyzer

FIXTURE = Path(__file__).parent / "fixtures" / "python_project" / "app.py"


def test_detects_aliased_socket_import():
    evidence = python_analyzer.scan_file(FIXTURE)
    matched = {e.matched for e in evidence}
    assert "socket.socket" in matched  # via `import socket as sk; sk.socket(...)`


def test_detects_capabilities():
    evidence = python_analyzer.scan_file(FIXTURE)
    caps = {e.capability for e in evidence}
    assert "network_inet" in caps
    assert "process_thread" in caps  # threading.Thread + os.fork
    assert "filesystem_io" in caps  # open() + sqlite3.connect


def test_bare_open_builtin_detected():
    text = 'def f():\n    with open("/tmp/x") as fh:\n        return fh.read()\n'
    evidence = python_analyzer.scan_text(text, "inline.py")
    assert any(e.matched == "open" for e in evidence)


def test_unrelated_code_yields_no_evidence():
    text = "def add(a, b):\n    return a + b\n"
    evidence = python_analyzer.scan_text(text, "inline.py")
    assert evidence == []


def test_syntax_error_returns_empty_not_raises():
    evidence = python_analyzer.scan_text("def bad(:\n", "broken.py")
    assert evidence == []
