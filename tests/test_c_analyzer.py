from pathlib import Path

from magi.analyzer import c_analyzer

FIXTURE = Path(__file__).parent / "fixtures" / "c_project" / "src" / "server.c"


def test_detects_network_calls():
    evidence = c_analyzer.scan_file(FIXTURE)
    matched = {e.matched for e in evidence}
    assert {"socket", "bind", "listen", "accept", "send", "recv"} <= matched


def test_detects_capabilities():
    evidence = c_analyzer.scan_file(FIXTURE)
    caps = {e.capability for e in evidence}
    assert "network_inet" in caps
    assert "filesystem_io" in caps
    assert "process_thread" in caps
    assert "ipc_shared_mmap" in caps


def test_ignores_comments():
    text = "// socket(AF_INET, SOCK_STREAM, 0);\nint x = 1;\n"
    evidence = c_analyzer.scan_text(text, "inline.c")
    assert evidence == []


def test_block_comment_ignored():
    text = "/* fopen(\"x\", \"r\"); */\nint y;\n"
    evidence = c_analyzer.scan_text(text, "inline.c")
    assert evidence == []


def test_token_matches_are_kind_token_not_call():
    evidence = c_analyzer.scan_file(FIXTURE)
    token_match = [e for e in evidence if e.matched == "MAP_SHARED"]
    assert token_match and token_match[0].kind == "token"
    call_match = [e for e in evidence if e.matched == "socket"]
    assert call_match and call_match[0].kind == "call"


def test_line_numbers_are_accurate():
    text = "int main(void) {\n    socket(1, 2, 3);\n    return 0;\n}\n"
    evidence = c_analyzer.scan_text(text, "inline.c")
    socket_ev = [e for e in evidence if e.matched == "socket"]
    assert len(socket_ev) == 1
    assert socket_ev[0].line == 2
