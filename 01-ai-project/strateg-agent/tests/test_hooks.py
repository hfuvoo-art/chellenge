# Тесты хуков Claude Code: без них запертые файлы правятся без вопроса, а битый stdin или ключ в команде ломают сессию или журнал.
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "tools" / "hooks"


def run_hook(name: str, payload, env_extra=None, raw: str | None = None):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", **(env_extra or {})}
    data = raw if raw is not None else json.dumps(payload, ensure_ascii=False)
    r = subprocess.run([sys.executable, str(HOOKS / name)], input=data.encode("utf-8"),
                       capture_output=True, env=env, cwd=str(ROOT), timeout=60)
    return r.returncode, r.stdout.decode("utf-8"), r.stderr.decode("utf-8")


def guard(tool, **tool_input):
    return run_hook("guard_rules.py", {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input})


def test_guard_asks_on_rules_edit():
    for tool, key, path in [("Edit", "file_path", "rules/style.md"), ("Write", "file_path", str(ROOT / "AGENTS.md")),
                            ("MultiEdit", "file_path", "prompts/extract.md"), ("Edit", "path", "tools/check.py"),
                            ("Edit", "file_path", "methods/jtbd.md"), ("Write", "file_path", "CLAUDE.md"),
                            ("Edit", "file_path", "tools/lock.py")]:
        code, out, _ = guard(tool, **{key: path})
        assert code == 0, path
        d = json.loads(out)["hookSpecificOutput"]
        assert d["hookEventName"] == "PreToolUse" and d["permissionDecision"] == "ask", path
        assert "lock.py --update" in d["permissionDecisionReason"]
    for cmd in ['echo x > rules/style.md', "sed -i 's/a/b/' AGENTS.md", "rm prompts/critic.md", "mv x.md methods/jtbd.md",
                "cp /tmp/a tools/check.py", "echo x | tee -a tools/lock.py", 'Set-Content -Path rules/safety.md -Value x',
                "git checkout -- rules/style.md", "python -c \"open('rules/style.md','w').write('x')\"",
                "cat a.md >> CLAUDE.md"]:
        code, out, _ = guard("Bash", command=cmd)
        assert code == 0 and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "ask", cmd


def test_guard_silent_for_other_files():
    for tool, ti in [("Edit", {"file_path": "projects/p1/brief.md"}), ("Write", {"file_path": "tools/status.py"}),
                     ("Edit", {"file_path": str(ROOT / "README.md")}), ("Edit", {"file_path": "/other/rules/x.md"}),
                     ("Bash", {"command": "cat rules/style.md"}), ("Bash", {"command": "python tools/check.py -p x"}),
                     ("Bash", {"command": "python tools/lock.py --verify"}), ("Bash", {"command": "ls methods && grep -n a AGENTS.md"}),
                     ("Bash", {"command": "python tools/check.py -p x > out.txt"}), ("Bash", {}), ("Edit", {})]:
        code, out, _ = guard(tool, **ti)
        assert (code, out.strip()) == (0, ""), (tool, ti)


def test_guard_broken_stdin_is_silent():
    for raw in ["", "не json", "[1, 2]", '{"tool_name": 5, "tool_input": "x"}']:
        code, out, _ = run_hook("guard_rules.py", None, raw=raw)
        assert (code, out.strip()) == (0, ""), raw
    for name in ["log_tool.py", "log_search.py"]:
        assert run_hook(name, None, raw="{{{")[0] == 0


def test_settings_json_valid_scripts_exist():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    hooks = s["hooks"]
    assert set(hooks) == {"SessionStart", "PreToolUse", "PostToolUse"}
    matchers = {(ev, g.get("matcher")) for ev, groups in hooks.items() for g in groups}
    assert ("PreToolUse", "Edit|Write|MultiEdit|Bash|PowerShell") in matchers
    assert ("PostToolUse", "Bash|PowerShell") in matchers and ("PostToolUse", "WebSearch") in matchers
    found = set()
    for groups in hooks.values():
        for g in groups:
            for h in g["hooks"]:
                assert h["type"] == "command" and isinstance(h["timeout"], int) and h["timeout"] > 0
                assert h["command"] == "python"
                for a in h["args"]:
                    p = ROOT / a.replace("${CLAUDE_PROJECT_DIR}/", "")
                    assert p.is_file(), a
                    found.add(p.name)
    assert found == {"session_start.py", "guard_rules.py", "log_tool.py", "log_search.py"}


def test_session_start_no_project(tmp_path):
    code, out, _ = run_hook("session_start.py", {"hook_event_name": "SessionStart"},
                            {"STRATEG_PROJECTS_DIR": str(tmp_path / "none")})
    assert code == 0 and "проект не выбран" in out.lower() and "playbooks/1-frame.md" in out and "Traceback" not in out


def test_session_start_with_project(tmp_project, tmp_path):
    pd = tmp_path / "projects"
    (pd / "CURRENT").write_text("p1", encoding="utf-8")
    code, out, _ = run_hook("session_start.py", {}, {"STRATEG_PROJECTS_DIR": str(pd)})
    assert code == 0 and "Проект: p1" in out


def _journal(pd: Path) -> list[dict]:
    p = pd / "p1" / "log.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


def test_post_hooks_write_events_and_mask_keys(tmp_project, tmp_path):
    pd = tmp_path / "projects"
    (pd / "CURRENT").write_text("p1", encoding="utf-8")
    env = {"STRATEG_PROJECTS_DIR": str(pd)}
    cmd = "python tools/ingest.py a.pdf --found-by user --api-key AQVNsecret123 -H 'Authorization: Bearer abc.def' sk-ABCdef123"
    assert run_hook("log_tool.py", {"tool_name": "Bash", "tool_input": {"command": cmd}}, env)[0] == 0
    run_hook("log_tool.py", {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}, env)
    run_hook("log_search.py", {"tool_name": "WebSearch", "tool_input": {"query": "eSIM Bearer sk-QQQ11111 тарифы"}}, env)
    ev = _journal(pd)
    assert [e["kind"] for e in ev] == ["tool", "search"]
    blob = json.dumps(ev, ensure_ascii=False)
    for secret in ("AQVNsecret123", "abc.def", "sk-ABCdef123", "sk-QQQ11111"):
        assert secret not in blob
    assert ev[0]["script"] == "ingest.py" and ev[1]["engine"] == "claude" and "eSIM" in ev[1]["query"]


def test_post_hooks_no_project_silent(tmp_path):
    env = {"STRATEG_PROJECTS_DIR": str(tmp_path / "none")}
    for name, p in [("log_tool.py", {"tool_input": {"command": "python tools/status.py"}}),
                    ("log_search.py", {"tool_input": {"query": "x"}})]:
        code, out, err = run_hook(name, p, env)
        assert (code, out.strip()) == (0, "") and "Traceback" not in err
    assert not (tmp_path / "none").exists()


def _ask(tool, **ti):
    code, out, _ = guard(tool, **ti)
    return code == 0 and bool(out.strip()) and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_guard_review_round1_asks():
    for p in ["tools/../rules/style.md", "../strateg-agent/rules/style.md", "./AGENTS.md"]:
        assert _ask("Edit", file_path=p), p
    for cmd in ["echo x>rules/style.md", "echo x>>AGENTS.md", "python tools/lock.py --update --reason x",
                "sed --in-place s/a/b/ AGENTS.md", "git restore rules", "git checkout rules", "git checkout -- methods",
                '"x" | Set-Content rules/a.md', "(1) | Out-File rules/a.md", "sc rules/a.md x", "echo x > tools/../rules/a.md",
                "rm -rf " + str(ROOT / "rules" / "old"), "rm -rf " + (ROOT / "prompts" / "x.md").as_posix(),
                "rm ../strateg-agent/methods/jtbd.md"]:
        assert _ask("Bash", command=cmd), cmd
    for cmd in ["Set-Content rules/x.md -Value 1", "Remove-Item prompts/critic.md", "python tools/lock.py --update --reason x"]:
        assert _ask("PowerShell", command=cmd), cmd


def test_guard_review_round1_silent():
    for cmd in ["rm -rf projects/x/rules/old", "python tools/lock.py --verify", "git status rules", "git diff rules/style.md",
                "cat projects/x/methods/a.md > /tmp/a"]:
        assert not _ask("Bash", command=cmd), cmd
    assert not _ask("PowerShell", command="python tools/check.py -p x")
    assert not _ask("PowerShell", command="Get-Content rules/style.md")


def test_settings_cover_powershell():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))["hooks"]
    assert any(g["matcher"] == "Edit|Write|MultiEdit|Bash|PowerShell" for g in s["PreToolUse"])
    assert any(g["matcher"] == "Bash|PowerShell" for g in s["PostToolUse"])


def test_post_hooks_mask_yandex_tokens_powershell(tmp_project, tmp_path):
    pd = tmp_path / "projects"
    (pd / "CURRENT").write_text("p1", encoding="utf-8")
    env = {"STRATEG_PROJECTS_DIR": str(pd)}
    cmd = "python tools/check.py -p x --h bearer abc.def y0_ABCDEFGHIJKLMN t1.9euelZqXXXXXXXXXX.yyyy"
    run_hook("log_tool.py", {"tool_name": "PowerShell", "tool_input": {"command": cmd}}, env)
    run_hook("log_search.py", {"tool_input": {"query": "q y0_ABCDEFGHIJKLMN t1.9euelZqXXXXXXXXXX.yyyy bearer zzz999"}}, env)
    ev = _journal(pd)
    assert [e["kind"] for e in ev] == ["tool", "search"] and ev[0]["script"] == "check.py"
    blob = json.dumps(ev)
    for secret in ("y0_ABCDEFGHIJKLMN", "t1.9euelZq", "abc.def", "zzz999"):
        assert secret not in blob
