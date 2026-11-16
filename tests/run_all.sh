#!/usr/bin/env bash
# Runs every test of both versions. Usage (from the project folder):  bash tests/run_all.sh
# Needs: python3 + pygame (Python version) and node (browser version).  Add "quick" to skip the slow full playthrough.
set -u
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
status=0
run() { name="$1"; shift; printf "%-34s" "$name"; out=$("$@" 2>&1); code=$?
        echo "$(echo "$out" | grep -E 'checks passed|problems|could not reach|bugs were caught|continuous run|could not finish' | tail -1 | cut -c1-110)  => $([ $code -eq 0 ] && echo PASS || echo FAIL)"
        [ $code -eq 0 ] || { status=1; echo "$out" | grep -E 'FAIL|FAILED|MISSED' | head -10; }; }
echo "=== Python version ==="
run "scenarios (170+ checks)"         python3 tests/scenarios.py mario_game
run "static_levels (all 50 levels)"   python3 tests/static_levels.py mario_game
run "bot_levels (terrain)"            python3 tests/bot_levels.py mario_game
[ "${1:-}" = "quick" ] || run "full_playthrough (level 1 -> end)" python3 tests/full_playthrough.py mario_game
run "python mutation check"           python3 tests/py_mutation_check.py mario_game
echo "=== Browser version (web.html) ==="
run "web_tests (headless game logic)" node tests/web_tests.js web.html
if [ "${1:-}" != "quick" ]; then
  WEB_BOT_LOG=$(mktemp); export WEB_BOT_LOG
  node tests/web_bot.js web.html > "$WEB_BOT_LOG" 2>&1; code=$?
  printf "%-34s" "web_bot: every level on its own"
  echo "$(grep -E 'could not finish' "$WEB_BOT_LOG" | tail -1 | cut -c1-110)  => $([ $code -eq 0 ] && echo PASS || echo FAIL)"
  [ $code -eq 0 ] || { status=1; grep -E 'FAIL|problem' "$WEB_BOT_LOG" | head -10; }
  # (the same run also plays ONE continuous game from a single New Game to the end screen; show that result on its own row)
  printf "%-34s" "web_bot: one continuous game"
  line=$(grep -E '^(ok|FAIL) +continuous run' "$WEB_BOT_LOG" | tail -1 | cut -c1-100)
  if echo "$line" | grep -q '^ok'; then echo "$line  => PASS"; else echo "${line:-the continuous run did not report}  => FAIL"; status=1; fi
fi
if [ -d tests/node_modules ] || [ -n "${CHROME_PATH:-}" ]; then
  run "web_browser_test (real phone)"  node tests/web_browser_test.js web.html
else echo "web_browser_test (real phone)   NOT RUN (run: cd tests && npm install)  => FAIL"; status=1; fi
run "web mutation check"              python3 tests/web_mutation_check.py web.html
echo; [ $status -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"; exit $status
