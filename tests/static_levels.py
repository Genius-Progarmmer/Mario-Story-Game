"""Static validation of all 50 levels (+ the same levels rebuilt for Continue at each checkpoint)."""
import os, sys, random, tempfile
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.abspath(sys.argv[1])); os.chdir(tempfile.mkdtemp())   # absolute path first: chdir changes the folder
import pygame
pygame.init(); pygame.display.set_mode((800, 600))
from settings import Config
from level import build_level, collect_solids
from world_objects import Pipe

SINGLE, DOUBLE = 147, 252          # measured with the real physics (see probe_baseline.py)
MAX_GAP = 160                      # widest gap between two neighbouring platforms that a normal (single) jump should cross
MAX_HOP = 286                      # widest gap even a double jump can cross (measured with the real physics);
                                   # platforms further apart than this are separate: nobody can hop between them
problems = []
def bad(msg): problems.append(msg)

def ground_top(plats, x):
    tops = [p.top for p in plats if p.height >= 50 and p.left <= x <= p.right]
    return min(tops) if tops else Config.ground_y

for lv in range(1, 51):
    variants = [None]
    first = build_level(lv, random.Random(lv * 0xDEAD_BEEF))
    variants += [c.world_x for c in first[3]]          # Continue from each checkpoint
    for start in variants:
        sx = 50 if start is None else start
        level = build_level(lv, random.Random(lv * 0xDEAD_BEEF), player_x=sx)
        plats, enemies, pipes, cps, blocks, boss, goal = level
        solids = collect_solids(level)
        tag = f"L{lv}{'' if start is None else '@cp'+str(start)}"
        for e in enemies:
            if any(e.rect.colliderect(s) for s in solids): bad(f"{tag}: enemy {e.rect} inside solid")
            under = pygame.Rect(e.rect.x, e.rect.bottom, e.rect.w, 4)
            if not any(under.colliderect(s) for s in solids): bad(f"{tag}: enemy {e.rect} floating (no floor)")
            if e.rect.right > goal.left or e.rect.left < 0: bad(f"{tag}: enemy outside play area x={e.rect.x}")
            if abs(e.rect.x - sx) < Config.enemy_spawn_distance_from_player: bad(f"{tag}: enemy too close to player")
        # player + companions respawn spot (same maths as Game._respawn)
        spots = [("mario", sx)] + [(f"comp{i}", sx - 55 * (i + 1)) for i in range(3)]
        for name, x in spots:
            x = max(0, x)
            r = pygame.Rect(x, 0, 32, 38); r.bottom = ground_top(plats, x)
            if any(r.colliderect(s) for s in solids): bad(f"{tag}: {name} respawn at x={x} inside a solid")
        for e in enemies:                # enemy touching the player on spawn would cost a life instantly
            r = pygame.Rect(sx, 0, 32, 38); r.bottom = ground_top(plats, sx)
            if r.colliderect(e.rect): bad(f"{tag}: enemy on top of the spawn point")
        if start is not None: continue
        # floating platforms: reachable from the ground, and neighbours reachable from each other
        floats = sorted(plats[1:], key=lambda p: p.x)
        for p in floats:
            if Config.ground_y - p.y > DOUBLE - 30: bad(f"{tag}: platform {p} too high ({Config.ground_y-p.y}px)")
        for a, b in zip(floats, floats[1:]):
            gap = b.left - a.right; rise = a.y - b.y
            # Two platforms close enough to hop between must be spaced so that a normal jump can do it.
            # A pipe in the gap is on purpose: the level never puts a platform over a pipe (it would block the jump).
            pipe_between = any(a.right - 40 < pp.world_x + Pipe.width and pp.world_x - 40 < b.left for pp in pipes)
            if 0 < gap <= MAX_HOP and not pipe_between and (gap > MAX_GAP or rise > SINGLE):
                bad(f"{tag}: spacing between platforms at {a.topleft} and {b.topleft} is unsuitable "
                    f"(gap={gap}px, a normal jump crosses {MAX_GAP}; rise={rise}px, max {SINGLE})")
        for b in blocks:
            if any(b.rect.colliderect(p) for p in plats[1:]): bad(f"{tag}: lucky block inside platform")
            for other in blocks:
                if other is not b and b.rect.colliderect(other.rect): bad(f"{tag}: two lucky blocks overlap")
        for i, c in enumerate(cps):
            for pp in pipes:
                if c.rect.colliderect(pp.shaft.inflate(20, 0)): bad(f"{tag}: checkpoint touching pipe")
        # headroom: a lucky block / platform must not leave a gap too small to walk through on the ground
        for s in solids:
            if s in plats: continue
            if s.bottom < Config.ground_y and Config.ground_y - s.bottom < 38 + 4 and s.top > Config.ground_y - 100:
                bad(f"{tag}: low obstacle {s} leaves less than Mario's height")
print(f"{len(problems)} problems")
from collections import Counter
SHOWN = 60
for m in problems[:SHOWN]: print(" ", m)
if len(problems) > SHOWN: print(f"  ... and {len(problems) - SHOWN} more not shown")
print(Counter(p.split(": ",1)[1].split(" ")[0] if ": " in p else p for p in problems))
print("RESULT:", "FAIL" if problems else "PASS")
sys.exit(1 if problems else 0)          # non-zero exit code = at least one problem was found
