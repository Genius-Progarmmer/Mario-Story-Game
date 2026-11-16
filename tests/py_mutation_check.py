"""Puts each fixed Python bug BACK into a copy of the source and verifies tests/scenarios.py notices.

    python tests/py_mutation_check.py mario_game

A bug counts as caught ONLY when scenarios.py really ran to its end and a check really failed.
If the test cannot run at all (crash, timeout, broken copy) that is reported as NOT RUN and the script fails.
Exit code 0 = every re-introduced bug was caught.
"""
import subprocess, sys, os, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from mutation_common import classify, self_test

SRC = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "mario_game")
ENV = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
# (what the old bug was, file, text of the fixed code, the old buggy code)
MUTANTS = [
 ("13 respawn keeps the old jump state", "game.py", "        mario.reset_for_respawn()\n",
  "        self._stop_moving(mario)\n        mario.pipe_sink_timer = 0\n        mario.dashing = False\n"),
 ("14 any number is accepted as a checkpoint", "save_system.py", "if checkpoint not in valid_spots:", "if not 0 <= checkpoint <= Config.level_width:"),
 ("15 block rewards use the global random", "level.py", "reward = random_generator.choice((\"fly\", \"crush\", \"jump\"))", "reward = random.choice((\"fly\", \"crush\", \"jump\"))"),
 ("3  logic runs one step per drawn frame (powers last longer at low fps)", "game.py", "steps = int(self.clock_accumulator / step_ms + 1e-9)", "steps = 1"),
 ("3  no cap on catching up after a freeze", "game.py", "if steps > Config.max_catch_up_steps:", "if False:"),
 ("4  crush ignores the vertical distance", "game.py", "                and abs(enemy_rect.centery - mario_rect.centery) < Config.crush_power_range_y)", "                and True)"),
 ("4  crush is checked with the old horizontal-only rule", "game.py", "if mario.power == \"crush\" and self._crush_reaches(enemy):",
  "if mario.power == \"crush\" and abs(enemy.rect.x - mario.rect.x) < Config.crush_power_range:"),
 ("5  the boss can leave its fight zone", "enemies.py", "        if self.rect.left < self.arena_left:", "        if False:"),
 ("5  the boss ignores pipes and blocks", "game.py", "boss.update(self.mario.rect.x, self.solids)", "boss.update(self.mario.rect.x, self.level[0])"),
 ("5  floating platforms may hang over the boss", "level.py", "        return is_boss and right > Config.level_width - Config.boss_arena_width", "        return False"),
 ("5  a good stomp on the boss can cost a life", "game.py", "            mario.rect.bottom = boss.rect.top\n            mario.subpixel_y = 0\n", ""),
 ("6  switching heroes leaves a twin on screen", "game.py", "                companion.appearance = current\n", "                pass\n"),
 ("6  the Princess / Yoshi cannot be chosen", "game.py", "        unlocked = [\"mario\"] + [companion.kind for companion in self.companions]",
  "        unlocked = [\"mario\"] + [companion.kind for companion in self.companions if companion.kind == \"luigi\"]"),
 ("8  Q says SAVED even if the save failed", "game.py", "                if not self._save_progress():\n                    self.pause_message", "                if False:\n                    self.pause_message"),
 ("8  a failed checkpoint autosave is hidden", "game.py", "                if self._save_progress():\n", "                self._save_progress()\n                if True:\n"),
 ("8  a failed new-level autosave is hidden", "game.py", "if not self._save_progress(keep_power=False):  # so the save", "if False:  # so the save"),
]

def run_scenarios(path):
    try:
        run = subprocess.run([sys.executable, os.path.join(HERE, "scenarios.py"), path], capture_output=True, text=True, env=ENV, timeout=900)
        return run.returncode, run.stdout, False
    except subprocess.TimeoutExpired:
        return None, "", True

self_test()
# 1. the UNCHANGED source must pass completely, otherwise "caught" would mean nothing
code, out, timed_out = run_scenarios(SRC)
if classify(code, out, timed_out) != "passed":
    print("ABORT: the unchanged source does not pass tests/scenarios.py, so this check cannot tell anything.")
    print("\n".join(out.splitlines()[-8:])); sys.exit(2)
print("baseline: unchanged source passes every check")

caught = missed = not_run = 0
for name, filename, fixed, bug in MUTANTS:
    work = tempfile.mkdtemp(); copy = os.path.join(work, "src"); shutil.copytree(SRC, copy, ignore=shutil.ignore_patterns("__pycache__"))
    path = os.path.join(copy, filename); text = open(path, encoding="utf-8").read()
    if text.count(fixed) < 1:
        print(f"NOT RUN {name}: pattern not found in {filename}, update this script"); not_run += 1; shutil.rmtree(work, ignore_errors=True); continue
    open(path, "w", encoding="utf-8").write(text.replace(fixed, bug, 1))
    code, out, timed_out = run_scenarios(copy)
    verdict = classify(code, out, timed_out)
    failed = [l[5:].split("  [")[0] for l in out.splitlines() if l.startswith("FAIL ")]
    shutil.rmtree(work, ignore_errors=True)
    if verdict == "failed":
        caught += 1; print(f"caught  {name:62s} -> {len(failed)} failing check(s); e.g. {failed[0]}")
    elif verdict == "passed":
        missed += 1; print(f"MISSED  {name}")
    else:
        not_run += 1; print(f"NOT RUN {name}: the test did not run to its end (crash / timeout) - this proves nothing\n        " + (out.strip().splitlines() or ["(no output)"])[-1][:150])
print(f"\n{caught}/{len(MUTANTS)} re-introduced bugs were caught" + (f", {missed} missed" if missed else "") + (f", {not_run} NOT RUN" if not_run else ""))
sys.exit(0 if caught == len(MUTANTS) else 1)
