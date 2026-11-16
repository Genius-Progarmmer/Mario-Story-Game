"""Bot walks every level from the start to the goal using the real physics (terrain only, no enemies)."""
import os, sys, random, tempfile
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.abspath(sys.argv[1])); os.chdir(tempfile.mkdtemp())   # absolute path first: chdir changes the folder
import pygame
pygame.init(); pygame.display.set_mode((800, 600))
from settings import Config
from player import Mario
from level import build_level, collect_solids

def run(level_number, start_x=50, max_frames=4000):
    rg = random.Random(level_number * 0xDEAD_BEEF)
    level = build_level(level_number, rg, player_x=start_x)
    solids = collect_solids(level); goal = level[6]
    m = Mario(start_x, 0); m.rect.bottom = 550
    stuck = 0; last_x = m.rect.x
    for f in range(max_frames):
        m.velocity_x = Config.player_speed; m.facing = 1
        probe = pygame.Rect(m.rect.right + 1, m.rect.y + 2, 6, m.rect.h - 4)
        if m.on_ground and probe.collidelist(solids) != -1: m.press_jump()
        elif not m.on_ground and m.velocity_y > 0 and m.jumps_left == 1 and probe.collidelist(solids) != -1: m.press_jump()
        m.update(solids)
        if m.rect.colliderect(goal) or m.rect.right >= goal.left: return True, f, m.rect.x
        stuck = stuck + 1 if m.rect.x == last_x else 0; last_x = m.rect.x
        if stuck > 120: return False, f, m.rect.x
    return False, max_frames, m.rect.x

bad = 0
for lv in range(1, 51):
    ok, f, x = run(lv)
    if not ok: bad += 1; print(f"L{lv}: BOT STUCK at x={x} (frame {f})")
print("levels where the bot could not reach the goal:", bad)
print("RESULT:", "FAIL" if bad else "PASS")
sys.exit(1 if bad else 0)               # non-zero exit code = the bot got stuck on at least one level
