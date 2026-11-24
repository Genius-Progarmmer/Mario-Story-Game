"""Checks the checks: puts each HTML bug BACK into a copy of web.html and verifies that
tests/web_tests.js notices.

    python tests/web_mutation_check.py web.html

A bug counts as caught ONLY when web_tests.js really ran to its end and a check really failed.
A run that crashed, timed out or never printed its summary is reported as NOT RUN and fails this script
(it used to be counted as "caught", which could hide a test that never ran).
Exit code 0 = every re-introduced bug was caught.
"""
import subprocess, sys, os, re, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from mutation_common import classify, self_test

SRC = sys.argv[1] if len(sys.argv) > 1 else "web.html"
html = open(SRC, encoding="utf-8").read()

# (what the old bug was, text of the fixed code, the old buggy code)
MUTANTS = [
 ("1  New Game keeps the old save",            "if(!sg(1,mario.lives,null,1,null,0,true)){", "if(false){"),
 ("2  Continue accepts a made-up checkpoint",  "if(cp!==null&&(!isInt(cp)||!checkpointSpots(d.lv).includes(cp)))return null;", "if(cp!==null&&!isInt(cp))return null;"),
 ("2  Continue shown for ANY save file",       "const hs=()=>!!lg();", "const hs=()=>!!localStorage.getItem(SAVE_KEY);"),
 ("2  lives are not checked",                  "if(!isInt(d.lives)||d.lives<1||d.lives>START_LIVES)return null;", ""),
 ("3  level 51 is counted and saved",          "if(curLv>=MAX_LV){playCS(", "if(false){playCS("),
 ("4  horizontal move jumps over thin walls",  "for(let i=0;i<Math.abs(sx);i++){\n    ent.rect.x+=dirX;", "ent.rect.x+=sx;\n  for(let i=0;i<Math.min(1,Math.abs(sx));i++){\n    ent.rect.x+=0;"),
 ("4  dash to the left is not cancelled by a wall", "if(stopDashOnWall && ent.dashing) ent.dashing = false;   // a dash to the left", "// a dash to the left"),
 ("5  tiny vertical movement forced to 1px",   "const steps=~~ent._ry; ent._ry-=steps;", "let steps=~~ent._ry; ent._ry-=steps; if(steps===0) steps = ent.vy>0 ? 1 : ent.vy<0 ? -1 : 0;"),
 ("5  no 'resting on ground' probe",           "if(!result.onGround && ent.vy>=0){", "if(false){"),
 ("6  dead boss can still hurt Mario",         "      if(b.alive){\n        if(b.punchRect&&", "      {\n        if(b.punchRect&&"),
 ("7  no end-of-level flag",                   "drawGoalFlag(gx,mario.fc);\n    }", "}"),
 ("7  pipe can hide the flag",                 "return hasGround && clearOfGoal && clearOfArena;", "return hasGround && clearOfArena;"),
 ("8  enemies on platforms are not created",   "enemies.push(new Mush(x,y-32,80));};", "};"),
 ("9  checkpoint does not save the power",     "sg(curLv,mario.lives,cpX,unlockedMax,mario.power,mario.powerT);flash=", "sg(curLv,mario.lives,cpX,unlockedMax);flash="),
 ("9  Pause+Q does not save the power",        "if(!sg(curLv,mario.lives,cpX,unlockedMax,mario.power,mario.powerT)){", "if(!sg(curLv,mario.lives,cpX,unlockedMax)){"),
 ("9  Continue does not restore the power",    "mario.power=d.pw;mario.powerT=d.pt;", ""),
 ("10 Continue starts at a fixed height",      "mario=new Player(0,0);standAt(mario.rect,sx);", "mario=new Player(sx,470);"),
 ("10 team always starts at the level start",  "standAt(c.rect,sx-c.offset);\n  if(blockedAt", "standAt(c.rect,50-c.offset);\n  if(blockedAt"),
 ("11 touch buttons work while paused",        "const canAct=()=>STATE==='playing'&&!!mario&&!pipeDying;", "const canAct=()=>!!mario;"),
 ("11 no pause button logic",                  "press('mcP',()=>{if(STATE==='playing')pauseGame();else if(STATE==='paused')resumeGame();});", ""),
 ("11 joystick does not set the keys",         "stickDir=dir;keys.ArrowLeft=dir<0;keys.ArrowRight=dir>0;", "stickDir=dir;"),
 ("12 stomping does not hurt the boss",        "if(b.hurt===0)hurtBoss(b,'STOMP!');", ""),
 ("12 text still says 5 hits",                 "txt('BOSS! PUNCH him (Z) or STOMP his head'", "txt('BOSS! Only PUNCH damages him — stomping just bounces you'"),
 ("respawn: jump state is not reset",          "mario.onGround=true;mario.wasg=true;mario.jl=2;mario.jheld=false;mario.jf=0;mario.squash=0;", "mario.squash=0;"),
 ("bot: a platform can block the jump over a pipe", "if(!pipes.some(pp=>pl.x<pp.lip.x+pp.lip.w+PIPE_ZONE_R&&pl.x+pl.w>pp.lip.x-PIPE_ZONE_L))continue;", "continue;"),
 ("bot: removed platforms leave enemies floating", "if(en.rect.y+en.rect.h===pl.y&&en.rect.x+en.rect.w>pl.x&&en.rect.x<pl.x+pl.w)enemies.splice(j,1);", ""),
 ("skip: Space on LEVEL / GAME OVER does nothing", "if(e.code==='Space'||e.code==='Enter')skipFalling();", ""),
 ("skip: tap on LEVEL / GAME OVER does nothing", "else if(STATE==='falling_text')skipFalling();", ""),
 ("16 lives start at 1 (Python: 3)",           "START_LIVES: 3,", "START_LIVES: 1,"),
 # ---- the ten fixes ----
 ("1  a held key repeats every command",             "if(!fresh)return;", ""),
 ("1  auto-repeat (e.repeat) is not recognised",     "const fresh=!e.repeat&&!kbHeld[e.code];", "const fresh=!kbHeld[e.code]&&false||true;"),
 ("1  a key that never came back up counts as new",  "const fresh=!e.repeat&&!kbHeld[e.code];", "const fresh=!e.repeat;"),
 ("2  new game keeps messages / shake / zoom",       "flash=null;shake=0;curZoom=1;hb=0;hd=1;", ""),
 ("2  new game keeps the held keys",                 "  clearAllKeys();\n  if(window.resetTouchInput)", "  if(window.resetTouchInput)"),
 ("2  new game keeps the old touch state",           "if(window.resetTouchInput)window.resetTouchInput();", ""),
 ("2  new game keeps old screens (cutscene / text)", "fa=null;faSub='';faNext=null;faT=0;cs=null;pipeDying=false;pauseMsg='';", ""),
 ("3  one logic step per drawn frame (old loop)",    "for(let i=0;i<steps;i++)update();", "update();"),
 ("3  a freeze is caught up for ever",               "if(n>CFG.CATCH_UP){n=CFG.CATCH_UP;clockAcc=0;}", "if(false){}"),
 ("4  crush ignores the vertical distance",          " && Math.abs((r.y+r.h/2)-(m.y+m.h/2))<CFG.CRUSH_RANGE_Y;", ";"),
 ("4  crush is wider when it starts than later",     "crushNearby();}\n", "for(const e of level.enemies)if(e.alive&&Math.abs(e.rect.x-mario.rect.x)<200)crushKill(e);}\n"),
 ("5  the boss can leave its fight zone",            "if(this.rect.x<this.arenaL){this.rect.x=this.arenaL;this.vx=0;this._rx=0;}", ""),
 ("5  the boss ignores pipes and blocks",            "b.upd(mario.rect.x,level.solids);", "b.upd(mario.rect.x,level.platforms);"),
 # (the extra filter "clearOfArena" in buildLv can never change a level today - 750 layouts tried, no pipe ever came near - so it is only
 #  a second safety net and has no mutant. The real protection is the free space at the end of a boss level:)
 ("5  a boss level has no free space at its end",   "const arenaBuffer = isBoss ? 1440 : 260;", "const arenaBuffer = 260;"),
 ("6  only Mario and Luigi can be chosen",           "const roster=HERO_ORDER.filter(", "const roster=['mario','luigi'].filter("),
 ("6  the hero you leave is shown twice",            "if(mate)mate._drawAs=prev;", ""),
 ("6  Princess / Yoshi are drawn as Mario",          "if(kind==='princess'){drawPrincess(", "if(false){drawPrincess("),
 ("7  menu: Enter does not start a new game",        "else menuNew();}", "}"),
 ("7  menu: Up / Down do nothing",                   "if(code==='ArrowUp'||code==='KeyW'){", "if(false){"),
 ("7  menu: Space does not confirm",                 "||code==='Space'){if(o[menuIdx]==='cont')", "){if(o[menuIdx]==='cont')"),
 ("8  Q says SAVED even if saving failed",          "if(!sg(curLv,mario.lives,cpX,unlockedMax,mario.power,mario.powerT)){", "if(!sg(curLv,mario.lives,cpX,unlockedMax,mario.power,mario.powerT)&&false){"),
 ("8  a storage that keeps nothing counts as saved", "return localStorage.getItem(SAVE_KEY)===text;", "return true;"),
 ("8  a failed checkpoint autosave is hidden",      "flash=saved?{t:'✔ CHECKPOINT!',d:80}:{t:'CHECKPOINT - but SAVE FAILED!',d:220};", "flash={t:'✔ CHECKPOINT!',d:80};"),
 ("D  debug: any password is accepted",              "if(real&&diff===0){", "if(true){"),
 ("D  debug: playing a debug level overwrites the real save", "if(debugActive)return true;", "if(false)return true;"),
 ("D  debug: the DEBUG button shows without a password", "if(debugPw())o.push('debug');", "o.push('debug');"),
 ("D  debug: the password box opens without a password", "  if(!debugPw())return;", "  "),
 ("D  debug: a cleared level goes on to the next level", "if(debugActive){debugReturn('LEVEL '+curLv+' CLEARED');return;}", "if(false){debugReturn('LEVEL '+curLv+' CLEARED');return;}"),
 ("L  a taken lucky block stays in the level",       "level.lbs=level.lbs.filter(lb=>!(lb.used&&lb.popT===0));", ""),
 ("L  lucky blocks are solid walls again",           "  // (Lucky Blocks are items, not walls: nobody is blocked by them. A taken block disappears, see update())\n", "  lbs.forEach(lb=>solids.push(lb.rect));\n"),
 ("8  a failed new-level autosave is hidden",       "if(!sg(curLv,START_LIVES,null,unlockedMax,null,0))flash=", "sg(curLv,START_LIVES,null,unlockedMax,null,0);if(false)flash="),
]

def run_tests(path):
    try:
        run = subprocess.run(["node", os.path.join(HERE, "web_tests.js"), path], capture_output=True, text=True, timeout=300)
        return run.returncode, run.stdout, False
    except subprocess.TimeoutExpired:
        return None, "", True

self_test()
# the UNCHANGED page must pass completely, otherwise "caught" would mean nothing
code, out, timed_out = run_tests(SRC)
if classify(code, out, timed_out) != "passed":
    print("ABORT: the unchanged web.html does not pass tests/web_tests.js, so this check cannot tell anything.")
    print("\n".join(out.splitlines()[-8:])); sys.exit(2)
print("baseline: unchanged web.html passes every check")

caught = missed = not_run = 0
for name, fixed, bug in MUTANTS:
    if html.count(fixed) < 1:
        print(f"NOT RUN {name}: pattern not found, update this script"); not_run += 1; continue
    mutant = html.replace(fixed, bug, 1) if name != "9  checkpoint does not save the power" else html.replace(fixed, bug)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(mutant); path = f.name
    code, out, timed_out = run_tests(path)
    os.unlink(path)
    verdict = classify(code, out, timed_out)
    failed = [l[5:].split("  [")[0] for l in out.splitlines() if l.startswith("FAIL ")]
    if verdict == "failed":
        caught += 1; print(f"caught  {name:52s} -> {len(failed)} failing check(s); e.g. {failed[0]}")
    elif verdict == "passed":
        missed += 1; print(f"MISSED  {name}")
    else:
        not_run += 1; print(f"NOT RUN {name}: the test did not run to its end (crash / timeout) - this proves nothing\n        " + ((out.strip().splitlines() or ["(no output)"])[-1][:150]))
print(f"\n{caught}/{len(MUTANTS)} re-introduced bugs were caught" + (f", {missed} missed" if missed else "") + (f", {not_run} NOT RUN" if not_run else ""))
sys.exit(0 if caught == len(MUTANTS) else 1)