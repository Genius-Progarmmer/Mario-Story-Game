"""Shared by py_mutation_check.py and web_mutation_check.py.

A "re-introduced bug" only counts as CAUGHT when the tests really RAN and a check really FAILED.
A test run that crashed, timed out or never reached its summary line has proven nothing about the bug,
so it is reported as NOT RUN and makes the whole check fail (it used to be counted as "caught").
"""
import re

SUMMARY = re.compile(r"(\d+)/(\d+) checks passed")


def classify(returncode, stdout, timed_out=False):
    """Returns 'passed' (all checks ran and passed), 'failed' (all checks ran, at least one failed),
    or 'not run' (the run crashed / timed out / never printed its summary: no verdict)."""
    if timed_out:
        return "not run"
    match = SUMMARY.search(stdout or "")
    if not match:
        return "not run"                               # no summary: the run stopped before the end
    passed, total = int(match.group(1)), int(match.group(2))
    if total == 0:
        return "not run"
    fail_lines = [line for line in stdout.splitlines() if line.startswith("FAIL ")]
    real_fails = [line for line in fail_lines if not line.startswith("FAIL CRASH")]
    crashed = len(real_fails) != len(fail_lines)
    if real_fails:
        # at least one real check failed. (A "CRASH" line after it is just the broken game taking the rest of the run down.)
        return "failed" if returncode != 0 else "not run"   # failures but exit code 0: inconsistent, do not trust
    if crashed:
        return "not run"                               # the ONLY problem is a crash: no check said anything about the bug
    if passed < total:
        return "not run"                               # the counts do not add up
    return "passed" if returncode == 0 else "not run"  # everything passed but a non-zero exit: inconsistent


def self_test():
    """The classifier checks itself first, so a broken classifier can never hide a missed bug."""
    ok_out = "PASS a\nPASS b\n\n2/2 checks passed\nRESULT: PASS\n"
    bad_out = "PASS a\nFAIL b  [x]\n\n1/2 checks passed\n  FAILED: b\nRESULT: FAIL\n"
    cases = [
        ("all checks pass", classify(0, ok_out), "passed"),
        ("a check fails", classify(1, bad_out), "failed"),
        ("crash before any output (the old false 'caught')", classify(1, "Traceback (most recent call last):\n  ImportError: boom\n"), "not run"),
        ("crash with empty output", classify(2, ""), "not run"),
        ("syntax error in the source", classify(1, "  File \"game.py\", line 3\n    def (\nSyntaxError: invalid syntax\n"), "not run"),
        ("timeout", classify(None, "", timed_out=True), "not run"),
        ("the ONLY problem is a crash (no check failed)", classify(1, "PASS a\nFAIL CRASH while running the checks: x\n\n1/2 checks passed\n"), "not run"),
        ("a real check failed, then the broken game crashed the rest", classify(1, "PASS a\nFAIL b  [x]\nFAIL CRASH while running the checks: x\n\n1/3 checks passed\n"), "failed"),
        ("zero checks", classify(0, "0/0 checks passed\n"), "not run"),
        ("failures but exit code 0", classify(0, bad_out), "not run"),
        ("all passed but non-zero exit", classify(1, ok_out), "not run"),
    ]
    wrong = [(name, got, want) for name, got, want in cases if got != want]
    for name, got, want in wrong:
        print(f"SELF-TEST FAILED: {name}: got {got!r}, wanted {want!r}")
    if wrong:
        raise SystemExit(2)
    print(f"classifier self-test: {len(cases)}/{len(cases)} ok")
