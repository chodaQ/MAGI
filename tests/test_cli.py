import json
from pathlib import Path

from magi.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_analyze_json_output(capsys):
    rc = main(["analyze", str(FIXTURES / "c_project"), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "network_inet" in payload["capabilities"]
    assert payload["files_scanned"] >= 2


def test_analyze_human_output(capsys):
    rc = main(["analyze", str(FIXTURES / "python_project")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "network_inet" in out


def test_build_writes_fragment(tmp_path, capsys):
    out_file = tmp_path / "out.config"
    rc = main([
        "build", str(FIXTURES / "c_project"),
        "--out", str(out_file),
    ])
    assert rc == 0
    assert out_file.is_file()
    content = out_file.read_text()
    assert "CONFIG_NET=y" in content
    out = capsys.readouterr().out
    assert "wrote Kconfig fragment" in out


def test_build_no_ai_flag_still_works(tmp_path):
    out_file = tmp_path / "out.config"
    rc = main([
        "build", str(FIXTURES / "c_project"), "--no-ai",
        "--out", str(out_file),
    ])
    assert rc == 0
    assert out_file.is_file()


def test_analyze_nonexistent_path_handled():
    rc = main(["analyze", "/nonexistent/path/xyz"])
    assert rc == 0  # analyze_path on a nonexistent path scans nothing, not an error
