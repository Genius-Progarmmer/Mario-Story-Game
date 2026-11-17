# Super Mario Bros – Made by Mehrsam

A 50-level Mario-style platformer written in Python with [pygame](https://www.pygame.org/).
Run through the levels, stomp or punch the enemies, collect Lucky Block powers, and beat the
boss at the end of every 10th level to unlock the goal.

## How to run

You need Python 3 (the game and its tests were run on Python 3.12 with pygame 2.6.1).

```bash
# 1. (optional but recommended) create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. install the library
pip install -r requirements.txt

# 3. start the game
python mario_game/main.py
```

Your progress is saved in a `saves/` folder, created in the folder you start the game from.
Start the game from the same folder each time if you want "Continue" to find your save.

There is also `web.html`, a separate version of the game that runs in a browser: just open the
file in your browser. It follows the same rules as the Python version (3 lives, a full set of lives on
every level, boss hurt by a stomp or a punch). Keyboard: arrows/`A` `D` to walk, `Space` to jump,
`Z` to punch, `T` to switch hero, `Esc` to pause. On a phone or tablet the side panels are hidden and
it shows on-screen controls: a joystick at the bottom left (push left/right to walk, push the same way twice
quickly to dash), a jump button (▲) at the bottom right with the punch button (👊) above it, small dash (⚡)
and switch-hero (⇄) buttons next to jump, and a pause button (⏸) that opens RESUME and SAVE & QUIT. Play in
landscape (in portrait the game pauses and asks you to rotate). The ⛶ button goes full screen; on an iPhone
use Share > Add to Home Screen and open the game from that icon. Its progress is stored in the browser (`localStorage`).

## Controls

| Key | What it does |
| --- | --- |
| `←` `→` or `A` `D` | Walk left / right |
| Double-tap `←` or `→` (or `A` / `D`) | **Dash** in that direction (has a short cooldown) |
| `Space`, `↑` or `W` | Jump. Press again in the air for a **double jump**. Hold the key for a higher jump |
| `Z` | **Punch** the enemy or boss in front of you |
| `T` | Switch to the next character you have unlocked (Mario > Luigi > Princess > Yoshi > Mario...). The character you leave takes the place of the one you switch to, so nobody is ever shown twice |
| `Esc` | Pause the game |

## Debug mode (developer only)

A password-protected mode to jump to **any level 1-50** and look for bugs. It exists only where a private `.env` file sets a password.

1. Copy `.env.example` to `.env` and set `DEBUG_PASSWORD=...` (`.env` is in `.gitignore`: it is never committed).
2. **Python:** nothing else. **Web:** run `python make_env_js.py` once (and again whenever you change `.env`). It writes
   `env.js`, which `web.html` loads (also in `.gitignore`).
3. In the main menu a **DEBUG** button appears. Enter the password, then pick a level: arrow keys (up / down = 10), type a
   number, or click / tap a level; `Enter` starts it. Boss levels are red.
4. While playing, **L** (or the **LEAVE LEVEL** button in the web version, or `Q` in the pause menu) goes back to the level
   picker. Reaching the goal or losing all lives also returns to the picker. `Esc` in the picker leaves debug mode.

A debug level always starts from its beginning with 3 lives, and **debug mode never writes the save file**, so your real
progress is untouched. A red *DEBUG* tag is always visible while playing.

> **Security:** without a `.env` there is no DEBUG button at all. In the **web** version the password is readable by anyone
> who can open your page or `env.js` (a browser cannot hide it), so it is a convenience for debugging on your own computer.
> **Never upload `env.js` to a public website.** Keep `bug.txt` (also in `.gitignore`) for your own bug notes.

In `web.html` every command (jump, double jump, dash, punch, switch hero, pause...) runs **once per key press**:
holding a key down does not repeat it (no double jump from a held `Space`, no dash from a held arrow, no hero
switching storm from a held `T`). Walking and flying still follow the held keys.

**In the main menu:** `↑` `↓` (or `W` `S`) to choose, `Enter` or `Space` to select. Without a save only
**NEW GAME** is offered, so `Enter` starts it. With a save, **CONTINUE** is highlighted first (so a quick `Enter`
never wipes your save by accident); `↑` / `↓` move to NEW GAME.

**While paused:** `Esc` or `Enter` continues the game, `Q` saves and goes back to the menu.

**In story scenes:** `Enter`, `Space` or `Esc` skips the cutscene; `Enter` or `Space` leaves the ending.

## How to play

- Reach the flag at the end of the level. Every level is 4800 pixels wide.
- Jump on an enemy's head or punch it to defeat it. Touching it from the side costs a life.
- You start with **3 lives**. After a death you come back at the last checkpoint with a short
  moment of invincibility. When all lives are gone it is GAME OVER.
- Hit a **Lucky Block** from below (or touch it from the side) to get a power for 3 seconds:
  `fly`, `crush` or `jump`. The game logic always runs at 60 steps per real second, even if the screen
  can only draw 30 frames per second, so a power really lasts 3 seconds and the game does not slow down
  (only a freeze longer than one second is dropped instead of caught up).
  `crush` defeats only enemies that are **close**: less than 90 px away horizontally **and** less than 60 px
  vertically (centre to centre). An enemy far above or below you is never hit. The range is the same when
  the power starts and for as long as it lasts.
- **Checkpoints** save your progress automatically (a new level is saved too). The game only says it saved when
  the save really worked: after writing, the file / browser storage is read back and compared. If it fails you
  see a clear message (`SAVE FAILED ...`), and **Save & quit** keeps you in the paused game instead of saying `SAVED!`. Starting a **New Game** replaces the old save,
  so "Continue" always resumes your latest game. A save is only accepted if its level, lives, power and
  checkpoint position are valid for that level; a damaged save simply makes "Continue" disappear.
- The boss fight happens in a fixed **fight zone**: the last 900 px of the level (from x = 3900). That zone has no
  pipes, floating platforms, Lucky Blocks or other enemies, and the boss never leaves it and cannot walk through
  pipes or blocks, however far away you run. A good stomp never costs a life (in the Python version a stomp also puts
  you on top of the boss, because a fast fall used to sink Mario into it and the next frame counted as a side touch).
- The last level of each chapter (10, 20, 30, 40, 50) has a **boss**. Stomp it or punch it (each hit takes
  1 HP); the goal stays locked until it is defeated. Watch out for its shells. (In `web.html` the boss
  attacks with punches instead of shells, and you can take 10 hits before losing a life. A boss that your
  last hit defeats can no longer hurt you.)
- Every 10 levels is a new chapter. Luigi and the Princess join you from level 11 (chapter 2) and Yoshi from level 21 (chapter 3).

## Tests

The tests run without a window (pygame's dummy video driver). Pass the path of the source folder:

```bash
python tests/scenarios.py        mario_game   # jump, dash, pipes, enemies, saves, pause, next level...
python tests/static_levels.py    mario_game   # all 50 levels: nothing inside walls or floating, sensible platform spacing
python tests/bot_levels.py       mario_game   # a bot can walk every level to the goal (terrain only)
python tests/full_playthrough.py mario_game   # a bot plays all 50 levels under the real game rules
node   tests/web_tests.js        web.html     # browser version: saves, walls, boss, mobile buttons... (needs Node.js)
node   tests/web_bot.js          web.html     # browser version: a bot plays all 50 levels, then ONE continuous game from a single New Game (WEB_BOT_DEBUG=1 explains each death)
node   tests/web_browser_test.js  web.html     # real Chromium with a phone emulated: layout, touches, pause, rotate (cd tests && npm install first)
bash   tests/run_all.sh                         # everything above, both versions, plus the 'put the bug back' checks
```

Every test ends with exit code `0` when all checks passed and a non-zero exit code when something
failed (the problems are printed first), so they can be used in a script or a CI job.

`full_playthrough.py` plays every level on its own and then makes one continuous run: the game is
started once at level 1 and the bot plays on until the game itself reaches level 50, defeats the
boss of level 50 and enters the ending, up to the final credits screen. The banners and chapter
cutscenes in between are played too, and a guard fails the test if the game is ever restarted.
At every level change it checks the level counter, the save file and the lives (each level starts
with a full set of lives, see `lives_on_arrival()` in that file).
It also accepts a level range, for example `python tests/full_playthrough.py mario_game 10 20`;
the continuous run only happens when the whole range 1 to 50 is tested.

`web_bot.js` does the same for the browser version: part 1 plays every level on its own, part 2 is **one
continuous game**: a single **New Game** started from the menu with `Enter`, then levels 1 to 50 without any restart,
all six story scenes in order, the final cutscene and the menu after the ending. At every level change it checks the
level counter, the lives (3 at the start of each level), the save file (and the checkpoint autosave); it fails
if the game is started more than once, a level is skipped, all lives are lost, or the ending is not reached.

The two `*_mutation_check.py` scripts put each fixed bug back into a copy of the game and check that the tests notice.
A bug only counts as **caught** when the test really ran to its end and a check really failed. A test that crashed, timed
out or printed no summary is reported as **NOT RUN** and makes the check fail (`tests/mutation_common.py`, which tests
itself first). Both scripts also first require the unchanged game to pass completely.

## Project layout

```
mario_game/
  main.py          entry point
  game.py          the Game class: states, input, game logic and all screens
  player.py        Mario: movement, jumping, dashing, punching
  enemies.py       the Mushroom enemy and the Turtle boss
  companions.py    Luigi, Princess and Yoshi
  level.py         level generation
  world_objects.py pipes, Lucky Blocks, checkpoints
  save_system.py   saving and loading progress
  settings.py      all game constants (Config) and colors
  utils.py         drawing helpers and the shared collision code
tests/             the tests described above
web.html           browser version
```
