"""Scenario tests that drive the real Game object headlessly with simulated key events."""
import os, sys, tempfile, json
# The tests must give the same result with or without the developer's private .env, so they point the game at a file that does not exist
# (the debug tests below write their own temporary .env).
NO_ENV_FILE = os.path.join(tempfile.gettempdir(), 'mario-test-no-such.env')
os.environ['MARIO_ENV_FILE'] = NO_ENV_FILE
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
SRC = os.path.abspath(sys.argv[1]); sys.path.insert(0, SRC)   # absolute: the next line changes the folder
os.chdir(tempfile.mkdtemp())                       # saves/ goes to a throw-away folder
import pygame
from settings import Config
import game as game_module
from game import Game
from save_system import load_game, has_save, save_game
from world_objects import Pipe

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))

# ---- fake keyboard ----
held = set()
class Keys:
    def __getitem__(self, k): return k in held
pygame.key.get_pressed = lambda: Keys()
def down(k): held.add(k); pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k))
def up(k): held.discard(k); pygame.event.post(pygame.event.Event(pygame.KEYUP, key=k))
def tap(k): pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k)); pygame.event.post(pygame.event.Event(pygame.KEYUP, key=k))

g = Game()
def frame(n=1):
    for _ in range(n):
        if g.state == "playing": g._play_frame()
        elif g.state == "paused": g.handle_pause(); g.draw_pause()
        elif g.state == "falling_text": g.handle_falling(); g.draw_falling()
        elif g.state == "cutscene": g.handle_cutscene(); g.draw_cutscene()
        elif g.state == "menu": g.handle_menu(); g.draw_menu()
def settle():
    for _ in range(5): frame()
def start(level=1, x=None):
    held.clear(); pygame.event.clear()
    g.new_game()
    g.current_level = level
    g._load_level(level, 50 if x is None else x)
    g.state = "playing"
    m = g.mario
    if x is not None: m.rect.x = x
    settle(); return m
def no_enemies():
    for e in g.level[1]: e.alive = False; e.squish = 0
    g.level[1].clear()

# =============== 1. JUMP / DOUBLE JUMP ===============
m = start(); no_enemies()
y0 = m.rect.bottom
down(pygame.K_SPACE); frame(); up(pygame.K_SPACE)
check("jump: leaves the ground", m.velocity_y < 0 and not m.on_ground)
check("jump: one jump used", m.jumps_left == 1)
apex1 = 0
for _ in range(60):
    frame(); apex1 = max(apex1, y0 - m.rect.bottom)
    if m.on_ground: break
check("jump: lands again and refills both jumps", m.on_ground and m.jumps_left == 2, f"ground={m.on_ground} jumps={m.jumps_left}")
m = start(); no_enemies(); y0 = m.rect.bottom
down(pygame.K_SPACE); frame(); frame(8)
down(pygame.K_SPACE); frame(); up(pygame.K_SPACE)
check("double jump: second jump works", m.jumps_left == 0)
apex2 = 0
for _ in range(20): frame(); apex2 = max(apex2, y0 - m.rect.bottom)
down(pygame.K_SPACE); frame(); 
check("double jump: a third jump in the air is ignored", m.jumps_left == 0)
up(pygame.K_SPACE)
for _ in range(120):
    frame()
    if m.on_ground: break
check("double jump: reaches higher than a single jump", apex2 > 147 * 0.9, f"apex2={apex2}")
check("double jump: lands and refills", m.on_ground and m.jumps_left == 2)

# =============== 2. DASH ===============
m = start(); no_enemies(); x0 = m.rect.x
tap(pygame.K_RIGHT); frame(); held.add(pygame.K_RIGHT); frame(2)
tap(pygame.K_RIGHT); frame()
check("dash: double tap starts a dash", m.dashing and m.velocity_x == Config.dash_speed, f"dashing={m.dashing} vx={m.velocity_x}")
dash_start_frame = m.frame_count
check("dash: the cooldown starts together with the dash", 0 < m.dash_cooldown <= Config.dash_cooldown, f"cooldown={m.dash_cooldown}")
xs = m.rect.x; frame(5); dash_move = m.rect.x - xs
check("dash: moves faster than walking", dash_move >= 5 * Config.dash_speed - 2, f"moved {dash_move}")
frame(Config.dash_duration + 2)
check("dash: ends after its duration", not m.dashing)
check("dash: the cooldown outlasts the dash itself", m.dash_cooldown > 0, f"cooldown={m.dash_cooldown}")
tap(pygame.K_RIGHT); frame(); tap(pygame.K_RIGHT); frame()
check("dash: cannot restart while cooling down", not m.dashing and m.dash_cooldown > 0, f"dashing={m.dashing} cooldown={m.dash_cooldown}")
for _ in range(Config.dash_cooldown * 2):
    if m.dash_cooldown == 0: break
    frame()
cooldown_frames = m.frame_count - dash_start_frame
check("dash: the cooldown lasts as long as Config.dash_cooldown says", m.dash_cooldown == 0 and abs(cooldown_frames - Config.dash_cooldown) <= 2, f"cooldown={m.dash_cooldown} after {cooldown_frames} frames, expected {Config.dash_cooldown}")
frame(3)                      # let the double-tap memory of the earlier taps run out
tap(pygame.K_RIGHT); frame(); tap(pygame.K_RIGHT); frame()
check("dash: works again once the cooldown is over", m.dashing, f"dashing={m.dashing}")
held.clear()
# dash into a pipe must stop at the wall (no tunnelling)
m = start(1, 900 - 120); no_enemies(); held.add(pygame.K_RIGHT)
pipe = g.level[2][0]
tap(pygame.K_RIGHT); frame(); tap(pygame.K_RIGHT)
for _ in range(60): frame()
check("dash: stops at the pipe wall, no tunnelling", m.rect.right <= pipe.shaft.left, f"right={m.rect.right} pipe={pipe.shaft.left}")
held.clear()

# =============== 3. PIPES (top / side / bottom), both modes ===============
def pipe_scenario(kills):
    Config.pipe_top_kills = kills
    m = start(1, 900 - 200); no_enemies(); pipe = g.level[2][0]
    lives0 = m.lives
    # SIDE: walk into the pipe
    held.add(pygame.K_RIGHT)
    for _ in range(80): frame()
    side_ok = m.rect.right == pipe.shaft.left and m.lives == lives0 and not g.pipe_dying
    held.clear(); frame(2)
    # TOP: land on the middle of the pipe from above and stand there for 2.5 seconds
    held.clear(); m.rect.centerx = pipe.shaft.centerx; m.rect.bottom = pipe.lip_center.top - 60
    m.velocity_y = 0; m.on_ground = False; m.invincibility_timer = 0
    for _ in range(40): frame()
    on_top = m.rect.bottom == pipe.lip_center.top and m.on_ground
    stood = 0
    for _ in range(150):
        frame(); stood += 1
        if g.pipe_dying or g.state != "playing" or m.lives != lives0: break
    return side_ok, on_top, m, lives0, g.pipe_dying or m.lives != lives0 or g.state != "playing"
side_ok, on_top, m, lives0, died = pipe_scenario(False)
check("pipe (ordinary obstacle): side contact is a solid wall without damage", side_ok)
check("pipe (ordinary obstacle): Mario can stand on top", on_top)
check("pipe (ordinary obstacle): standing on top costs NO life", on_top and not died and m.lives == lives0, f"lives={m.lives}")
# JUMP ONTO the pipe from the ground with a human-style timing
Config.pipe_top_kills = False
m = start(1, 900 - 70); no_enemies(); pipe = g.level[2][0]
held.add(pygame.K_RIGHT); down(pygame.K_SPACE); frame(8); held.discard(pygame.K_RIGHT)   # hold jump, steer over the pipe, stop
landed_on_top = False
for _ in range(60):
    frame()
    if m.on_ground and m.rect.bottom == pipe.lip_center.top: landed_on_top = True; break
up(pygame.K_SPACE); held.clear()
check("pipe: Mario can jump up from the ground onto the top", landed_on_top, f"x={m.rect.x} bottom={m.rect.bottom}")
# BOTTOM: a pipe hanging in the air with a floor far below (synthetic)
Config.pipe_top_kills = False
m = start(1, 300); no_enemies()
hanging = Pipe(300 - 10, 450)           # body spans y 388..450, standing room underneath
g.level[2].append(hanging); g.solids.extend((hanging.shaft, hanging.lip_center))
m.rect.x = 300 + 10; m.rect.bottom = Config.ground_y; settle()
lives0 = m.lives
down(pygame.K_SPACE); frame()
hit_ceiling = False
for _ in range(40):
    frame()
    if m.rect.top == hanging.shaft.bottom: hit_ceiling = True
up(pygame.K_SPACE)
check("pipe: hitting it from below stops Mario (solid ceiling)", hit_ceiling)
check("pipe: hitting it from below costs no life", m.lives == lives0 and not g.pipe_dying)
# kill mode keeps working when switched on (feature switch still honoured)
side_ok, on_top, m, lives0, died = pipe_scenario(True)
check("pipe (pipe_top_kills=True): side is still harmless", side_ok)
check("pipe (pipe_top_kills=True): standing on top kills, as the switch says", on_top and died)
Config.pipe_top_kills = False

# =============== 4. ENEMIES: stomp / side hit / punch ===============
from enemies import Mushroom
def add_enemy_at(x, bottom=Config.ground_y):
    e = Mushroom(x, bottom - 30, 0); e.speed = 0; g.level[1].append(e); return e
m = start(1, 200); no_enemies(); e = add_enemy_at(300)
# stomp from above
m.rect.x = 300; m.rect.bottom = 520; m.velocity_y = 6; m.on_ground = False; m.invincibility_timer = 0
lives0 = m.lives; frame(3)
check("enemy: stomping from above kills it and Mario bounces", not e.alive and m.velocity_y < 0 and m.lives == lives0)
# side contact
m = start(1, 200); no_enemies(); e = add_enemy_at(260)
held.add(pygame.K_RIGHT); lives0 = m.lives
for _ in range(30):
    frame()
    if m.lives < lives0: break
held.clear()
check("enemy: side contact costs exactly one life", m.lives == lives0 - 1, f"lives={m.lives}")
check("enemy: Mario respawns with invincibility", m.invincibility_timer > 0)
lives1 = m.lives; e.rect.x = m.rect.x; frame(3)
check("enemy: no damage while invincible", m.lives == lives1)
# punch
m = start(1, 200); no_enemies(); e = add_enemy_at(m.rect.right + 10)
tap(pygame.K_z); frame(3)
check("enemy: punch kills an enemy in front", not e.alive)

# a defeated enemy stays on screen as a squashed sprite for a few frames and then disappears
m = start(1, 200); no_enemies(); e = add_enemy_at(300)
draws = []                                    # how often the game really draws this enemy, one entry per frame
real_draw = e.draw
def spy_draw(*args, **kwargs): draws.append(1); return real_draw(*args, **kwargs)
e.draw = spy_draw
m.rect.x = 300; m.rect.bottom = 520; m.velocity_y = 6; m.on_ground = False; m.invincibility_timer = 0
for _ in range(5):
    frame()
    if not e.alive: break
check("enemy squish: the stomp defeats the enemy and starts the squash timer", not e.alive and e.squish == Config.enemy_squish_frames,
      f"alive={e.alive} squish={e.squish}")
e.speed = Config.enemy_speed                  # if the game ever moved a defeated enemy, now it would show
x0, y0 = e.rect.x, e.rect.y
shown, squish_seen = [], []
for _ in range(Config.enemy_squish_frames):   # 20 frames
    draws.clear(); frame(); shown.append(len(draws)); squish_seen.append(e.squish)
check("enemy squish: the timer counts down every frame while the enemy is defeated",
      squish_seen == list(range(Config.enemy_squish_frames - 1, -1, -1)), f"squish per frame: {squish_seen}")
check("enemy squish: after 20 frames the timer is zero", e.squish == 0, f"squish={e.squish}")
check("enemy squish: the squashed enemy is still drawn while the timer runs", all(n == 1 for n in shown[:-1]), f"draws per frame: {shown}")
check("enemy squish: after 20 frames the enemy is no longer drawn", shown[-1] == 0, f"draws in the last frame: {shown[-1]}")
draws.clear(); frame(5)
check("enemy squish: it stays gone afterwards", not draws and e.squish == 0 and not e.alive, f"draws={len(draws)} squish={e.squish}")
check("enemy squish: a defeated enemy never moves", (e.rect.x, e.rect.y) == (x0, y0), f"{(x0, y0)} -> {(e.rect.x, e.rect.y)}")

# =============== 5. LOSING LIVES AND DYING ===============
m = start(1, 200); no_enemies()
m.rect.y = Config.screen_height + 200; frame()
check("death: falling into a pit costs a life and respawns", m.lives == 2 and g.state == "playing" and m.rect.y < 600)
m.rect.y = Config.screen_height + 200; frame()
check("death: second death leaves 1 life", m.lives == 1)
m.rect.y = Config.screen_height + 200; frame()
check("death: last life lost shows GAME OVER", m.lives == 0 and g.state == "falling_text" and g.fall_next_state == "menu")
for _ in range(600):
    frame()
    if g.state == "menu": break
check("death: after GAME OVER the menu is shown", g.state == "menu")

# =============== 6. SAVE / LOAD / NEW GAME / CONTINUE ===============
if os.path.exists(Config.save_file_path): os.remove(Config.save_file_path)
g._build_menu(); g.state = "menu"
check("menu: no Continue without a save", "Continue" not in g.menu_options)
m = start(1, 100); no_enemies()
cp = g.level[3][0]
m.rect.x = cp.world_x - 40; settle()
held.add(pygame.K_RIGHT)
for _ in range(40): frame()
held.clear()
check("save: touching a checkpoint stores it", g.checkpoint_x == cp.world_x and has_save())
data = load_game()
check("save: file content is right", data and data["level"] == 1 and data["lives"] == 3 and data["checkpoint"] == cp.world_x, str(data))
m.power = "jump"; m.power_timer = 100; m.lives = 2
g.state = "paused"; g.handle_pause(); pygame.event.clear()
tap(pygame.K_q); g.handle_pause()
check("save: Q in the pause menu saves and goes to the menu", g.state == "falling_text" and g.fall_next_state == "menu")
data = load_game()
check("save: lives and power are stored", data["lives"] == 2 and data["power"] == "jump" and data["power_timer"] == 100, str(data))
for _ in range(600):
    frame()
    if g.state == "menu": break
check("menu: Continue appears when there is a save", "Continue" in g.menu_options)
g.selected_index = g.menu_options.index("Continue"); tap(pygame.K_RETURN); frame()
m = g.mario
check("continue: restores level, lives, power and checkpoint", g.state == "playing" and g.current_level == 1 and m.lives == 2 and m.power == "jump" and g.checkpoint_x == cp.world_x and abs(m.rect.x - cp.world_x) < 5, f"x={m.rect.x}")
# new game must forget the old run
m.lives = 1; g.checkpoint_x = 999; g.flash = ("old", 50)
g.state = "menu"; g._build_menu()
g.selected_index = g.menu_options.index("New Game"); tap(pygame.K_RETURN); frame()
m = g.mario
check("new game: starts clean (3 lives, level 1, no checkpoint/flash/power)", g.state == "playing" and m.lives == 3 and g.current_level == 1 and g.checkpoint_x is None and g.flash is None and m.power is None and m.rect.x < 100)
data = load_game()
check("new game: the old save is replaced at once by a fresh one", data is not None and data["level"] == 1 and data["lives"] == 3 and data["checkpoint"] is None and data["power"] is None, str(data))
# the old bug: an old game on level 7 survived "New Game" and came back through "Continue"
save_game(7, 2, 2675, None, 0)   # 2675 = a real checkpoint of level 7
g.state = "menu"; g._build_menu()
g.selected_index = g.menu_options.index("New Game"); tap(pygame.K_RETURN); frame()
m = g.mario
m.rect.y = Config.screen_height + 200; frame()
m.rect.y = Config.screen_height + 200; frame()
m.rect.y = Config.screen_height + 200; frame()
for _ in range(600):
    frame()
    if g.state == "menu": break
check("new game: losing right away leaves the menu again", g.state == "menu")
g.selected_index = g.menu_options.index("Continue"); tap(pygame.K_RETURN); frame()
check("new game: Continue after it starts the NEW game, not the old level-7 one", g.state == "playing" and g.current_level == 1 and g.mario.lives == 3 and g.checkpoint_x is None, f"level={g.current_level} lives={g.mario.lives} checkpoint={g.checkpoint_x}")
# if the old save cannot be overwritten, it must at least be deleted
save_game(7, 2, 2675, None, 0)   # 2675 = a real checkpoint of level 7
real_save_game = game_module.save_game
game_module.save_game = lambda *args, **kwargs: False
g.new_game()
game_module.save_game = real_save_game
check("new game: if the save cannot be written, the old one is deleted", not has_save())
# corrupt save is rejected
open(Config.save_file_path, "w").write("{broken")
check("save: corrupt file is ignored", load_game() is None and not has_save())
g._build_menu(); g.state = "menu"
g.menu_options = ["New Game", "Continue", "Quit"]; g.selected_index = 1; tap(pygame.K_RETURN); frame()
check("continue: a bad save does not crash and removes Continue", g.state == "menu" and "Continue" not in g.menu_options)

# =============== 7. PAUSE IN THE MIDDLE OF MOVEMENT / ATTACK ===============
def snapshot(m):
    return (m.rect.x, m.rect.y, m.velocity_x, m.velocity_y, m.punch_timer, m.jumps_left, m.dash_timer, m.frame_count, m.invincibility_timer, m.power_timer)
m = start(1, 200); no_enemies()
held.add(pygame.K_RIGHT); down(pygame.K_SPACE); frame(); up(pygame.K_SPACE); frame(5)
tap(pygame.K_z); frame()
assert m.punch_timer > 0 and not m.on_ground
tap(pygame.K_ESCAPE); frame()
check("pause: ESC pauses in mid-air during a punch", g.state == "paused")
snap = snapshot(m); enemies_snap = [e.rect.copy() for e in g.level[1]]
# hammer every input while paused
for _ in range(30):
    for k in (pygame.K_SPACE, pygame.K_z, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_UP, pygame.K_d, pygame.K_t): tap(k)
    frame()
check("pause: no movement, jump, punch or dash while paused", snapshot(m) == snap, f"{snap} -> {snapshot(m)}")
check("pause: enemies and world are frozen too", [e.rect for e in g.level[1]] == enemies_snap)
held.clear(); frame()
tap(pygame.K_ESCAPE); frame()
check("pause: ESC resumes", g.state == "playing")
frame(60)
check("pause: after resume the game continues normally (lands)", m.on_ground and m.punch_timer == 0)
# ESC and SPACE in the same frame: the jump must not happen
m = start(1, 200); no_enemies(); held.clear()
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
y0 = m.rect.y; frame()
check("pause: keys in the same frame as ESC are ignored (no jump, no punch)", g.state == "paused" and m.rect.y == y0 and m.punch_timer == 0 and m.jumps_left == 2)
# jump key released during pause
m = start(1, 200); no_enemies()
down(pygame.K_SPACE); frame(3)
tap(pygame.K_ESCAPE); frame(); up(pygame.K_SPACE); frame(5)
tap(pygame.K_ESCAPE); frame()
check("pause: releasing jump during pause does not leave the jump 'held'", g.state == "playing" and not m.jump_held)
# double-tap memory does not survive a pause
m = start(1, 200); no_enemies(); held.clear()
tap(pygame.K_RIGHT); frame(); tap(pygame.K_ESCAPE); frame(); tap(pygame.K_ESCAPE); frame()
tap(pygame.K_RIGHT); frame()
check("pause: a tap before and a tap after the pause is not a dash", not m.dashing)

# =============== 8. NEXT LEVEL ===============
m = start(1, 200); no_enemies(); goal = g.level[6]
m.rect.x = goal.x - 10; frame(2)
check("next level: reaching the goal advances to level 2", g.current_level == 2 and g.state == "falling_text" and g.fall_next_state == "playing")
check("next level: progress is saved", load_game()["level"] == 2)
for _ in range(600):
    frame()
    if g.state == "playing": break
check("next level: gameplay resumes in level 2 at the start with no checkpoint", g.state == "playing" and g.mario.rect.x < 100 and g.checkpoint_x is None)
# chapter change -> cutscene
start(10, 200); no_enemies(); g.level[5].alive = False
g.mario.rect.x = g.level[6].x - 10; frame(2)
check("next level: level 10 -> 11 plays the chapter cutscene", g.current_level == 11 and g.state == "cutscene" and len(g.companions) == 2)
# boss keeps the goal locked
start(10, 200); no_enemies(); boss = g.level[5]
g.mario.rect.x = g.level[6].x - 10; g.mario.invincibility_timer = 9999; frame(2)
check("boss level: goal stays locked while the boss lives", g.current_level == 10)

# the last hit on the boss must not cost Mario a life, even though he is still touching its body
def boss_next_to_mario(health):
    """Level 10 boss with `health` hits left, Mario facing it and overlapping its body, no shells, not invincible."""
    mm = start(10, 200); no_enemies(); b = g.level[5]
    b.health = health; b.hurt = 0; b.projectiles.clear()
    mm.rect.right = b.rect.left + 12; mm.rect.bottom = b.rect.bottom; mm.facing = 1
    mm.invincibility_timer = 0; mm.punch_timer = 0; mm.velocity_y = 0
    return mm, b
m, boss = boss_next_to_mario(1); m.punch_timer = Config.punch_duration; lives = m.lives
lost = g._update_boss()
check("boss last punch: the punch defeats the boss", not boss.alive)
check("boss last punch: touching the dead boss does not cost a life", not lost and m.lives == lives and g.state == "playing",
      f"lost={lost} lives {lives}->{m.lives} state={g.state}")
check("boss last punch: the goal unlocks afterwards", not (g.level[5] and g.level[5].alive))
m, boss = boss_next_to_mario(1); m.rect.bottom = boss.rect.top + 6; m.rect.centerx = boss.rect.centerx; m.velocity_y = 6; lives = m.lives
lost = g._update_boss()
check("boss last stomp: defeats the boss and costs no life", not boss.alive and not lost and m.lives == lives, f"alive={boss.alive} lost={lost} lives {lives}->{m.lives}")
m, boss = boss_next_to_mario(3); lives = m.lives
lost = g._update_boss()
check("boss alive: touching its body takes ONE HEART, not a life (like the HTML game)", boss.alive and not lost and m.lives == lives and m.boss_hits == 1 and m.invincibility_timer == Config.boss_hit_invincibility, f"lost={lost} lives {lives}->{m.lives} hits={m.boss_hits}")
m, boss = boss_next_to_mario(3); m.punch_timer = Config.punch_duration; lives = m.lives
lost = g._update_boss()
check("boss not on its last hit: a punch hurts it and touching it takes one heart (no life lost)", boss.alive and boss.health == 2 and not lost and m.lives == lives and m.boss_hits == 1,
      f"health={boss.health} lost={lost} lives {lives}->{m.lives} hits={m.boss_hits}")

# =============== 8b. THE LAST LEVEL HAS NO NEXT LEVEL ===============
start(Config.max_levels, 200); no_enemies(); g.level[5].alive = False
save_game(Config.max_levels, 3, None, None, 0)      # what entering level 50 really saved
g.mario.rect.x = g.level[6].x - 10; frame(2)
check("last level: finishing it starts the ending", g.state == "ending" and g.ending_stage == 1, f"state={g.state}")
check("last level: the level counter does not go past the last level", g.current_level == Config.max_levels, f"level={g.current_level}")
data = load_game()
check("last level: no level 51 is written; the save stays valid", data is not None and data["level"] == Config.max_levels and has_save(), str(data))
# the level before it still advances and saves normally
start(Config.max_levels - 1, 200); no_enemies(); g.level[5] and setattr(g.level[5], "alive", False)
g.mario.rect.x = g.level[6].x - 10; frame(2)
check("last level: level 49 still advances to 50 and saves it", g.current_level == Config.max_levels and load_game()["level"] == Config.max_levels)

# =============== 9. LUCKY BLOCKS ===============
m = start(1); no_enemies(); blk = g.level[4][0]
m.rect.x = blk.rect.x; m.rect.bottom = Config.ground_y; settle()
down(pygame.K_SPACE); frame(); up(pygame.K_SPACE); frame(40)
check("lucky block: hitting it from below gives a power", blk.used and m.power == blk.reward and m.power_timer > 0, f"used={blk.used}")
m = start(1); no_enemies(); blk = g.level[4][0]; blk.used = False
m.rect.x = blk.rect.right + 30; m.rect.bottom = blk.rect.bottom; m.on_ground = False; held.add(pygame.K_LEFT)
frame(40); held.clear()
check("lucky block: touching it from the side works", blk.used)

# =============== 13-15. respawn state, checkpoint validation, reward seed ===============
# 13. dying in mid-air with both jumps used must not block the first jump after the respawn
m = start(); no_enemies()
m.jumps_left = 0; m.jump_held = True; m.jump_frames = 9; m.on_ground = False; m.was_on_ground = False
m.velocity_y = -8; m.squash = 0.5; m.dashing = True; m.punch_timer = 7
g._take_life()                                   # respawn at the start of the level
check("respawn: jump state is reset", m.jumps_left == 2 and not m.jump_held and m.jump_frames == 0 and m.on_ground and not m.dashing and m.punch_timer == 0 and m.squash == 0,
      f"jumps={m.jumps_left} held={m.jump_held} ground={m.on_ground}")
down(pygame.K_SPACE); frame(); up(pygame.K_SPACE)
check("respawn: Mario can jump on the very first frame after appearing", m.velocity_y < 0 and m.jumps_left == 1, f"vy={m.velocity_y}")

# 14. a checkpoint must be one of the level's own checkpoints
from level import checkpoint_positions
import save_system
real_spots = checkpoint_positions(7)
check("save check: every real checkpoint of the level is accepted", all(save_system.validate_save_data({"level": 7, "lives": 3, "checkpoint": spot}) for spot in real_spots))
check("save check: no checkpoint (None) is accepted", save_system.validate_save_data({"level": 7, "lives": 3, "checkpoint": None})["checkpoint"] is None)
for bad in (4600, 0, 1500, real_spots[0] + 1, -5, 2675.0 + 0.5, "2675", True):
    try:
        save_system.validate_save_data({"level": 7, "lives": 3, "checkpoint": bad}); accepted = True
    except ValueError:
        accepted = False
    check(f"save check: checkpoint {bad!r} is rejected", not accepted)
save_game(1, 3, 4600, None, 0)                  # the exact file from the bug report
check("save check: a save with checkpoint 4600 gives no Continue", load_game() is None and not has_save())
g.state = "menu"; g._build_menu()
check("save check: ...and the menu has no Continue entry", "Continue" not in g.menu_options)

# 15. the same level always hides the same reward in every Lucky Block
import random as random_module
from level import build_level, level_random
def rewards_of(level_number):
    return [(block.rect.x, block.rect.y, block.reward) for block in build_level(level_number, level_random(level_number))[4]]
state_before = random_module.getstate()
all_same = True
for number in range(1, Config.max_levels + 1):
    random_module.seed(number)                   # a different global random state each time
    first = rewards_of(number)
    random_module.seed(number + 1000)
    all_same = all_same and first == rewards_of(number) and len(first) >= 1
random_module.setstate(state_before)
check("rewards: all 50 levels are rebuilt identically (blocks AND rewards), whatever the global random state", all_same)
check("rewards: blocks hide only valid powers", all(reward in ("fly", "crush", "jump") for number in range(1, 51) for _x, _y, reward in rewards_of(number)))


# =====================================================================================================
# NEW CHECKS: game clock, crush range, boss fight zone, hero switching, save failures
# =====================================================================================================
import save_system, companions as companions_module, player as player_module
from player import Mario
from enemies import Mushroom

# ---- A. game clock: logic runs at 60 steps per REAL second, whatever the frame rate ----
def steps_over(fps, seconds, jitter=0.0):
    g.clock_accumulator = 0.0; total = 0
    for i in range(int(fps * seconds)):
        total += g.steps_for(1000.0 / fps + (jitter if i % 2 else -jitter))
    return total
for fps in (144, 120, 60, 30, 20, 15, 10):
    got = steps_over(fps, 10)
    check(f"clock: at {fps} fps the logic still runs 600 steps in 10 real seconds", abs(got - 600) <= 2, got)
check("clock: ...also with an uneven frame time (60 fps with jitter)", abs(steps_over(60, 10, 2.0) - 600) <= 2)
g.clock_accumulator = 0.0
check("clock: a 10 second freeze is capped (no endless catch-up)", g.steps_for(10000) == Config.max_catch_up_steps)
check("clock: ...and the backlog is dropped", g.steps_for(16.7) == 1)
g.clock_accumulator = 0.0
check("clock: time going backwards runs nothing", g.steps_for(-50) == 0)

for fps in (60, 30, 20):
    m = start(); no_enemies(); g.clock_accumulator = 0.0
    m.power = "jump"; m.power_timer = Config.power_duration_frames
    frame_ms = 1000.0 / fps; elapsed = 0.0
    while m.power and elapsed < 6000:
        g.advance(frame_ms); elapsed += frame_ms
    check(f"powers: at {fps} fps a 3 second power lasts 3 real seconds (+-1 frame)",
          m.power is None and abs(elapsed - 3000) <= frame_ms + 17, f"{elapsed:.0f} ms")
def walk_distance(fps):
    m = start(); no_enemies(); g.clock_accumulator = 0.0; x0 = m.rect.x
    held.add(pygame.K_RIGHT)
    for _ in range(int(fps * 0.5)): g.advance(1000.0 / fps)
    held.discard(pygame.K_RIGHT); return m.rect.x - x0
d60, d30, d20 = walk_distance(60), walk_distance(30), walk_distance(20)
check("speed: walking for 0.5 s covers the same distance at 60, 30 and 20 fps",
      abs(d60 - d30) <= 12 and abs(d60 - d20) <= 18 and d60 > 130, f"{d60} / {d30} / {d20}")
m = start(); no_enemies(); g.clock_accumulator = 0.0; m.punch()
for _ in range(9): g.advance(1000.0 / 30)
check("speed: a punch (18 steps) lasts 0.3 real seconds at 30 fps too", m.punch_timer == 0, m.punch_timer)

# ---- B. CRUSH: near in BOTH directions; the same range at the start and while it lasts ----
def crush_setup(dx, dy, power=True):
    m = start(); no_enemies(); m.invincibility_timer = 9999
    m.rect.x = 1000; m.rect.bottom = Config.ground_y; m.velocity_y = 0
    enemy = Mushroom(m.rect.x + dx, m.rect.y + 6 + dy, 120); g.level[1].append(enemy)
    if power: m.power = "crush"; m.power_timer = 180
    return enemy
e = crush_setup(40, 0); g._update_enemies(); check("crush: an enemy right next to Mario is defeated", not e.alive)
e = crush_setup(40, -250); g._update_enemies(); check("crush: an enemy 250px ABOVE Mario is NOT defeated (the reported bug)", e.alive)
e = crush_setup(40, -120); g._update_enemies(); check("crush: ...nor one 120px above", e.alive)
m = start(); no_enemies(); m.rect.x = 1000; m.rect.y = 150; m.power = "crush"; m.power_timer = 180; m.invincibility_timer = 9999
low = Mushroom(1040, Config.ground_y - 30, 120); g.level[1].append(low); g._update_enemies()
check("crush: an enemy far BELOW Mario is NOT defeated either", low.alive)
e = crush_setup(70, 0); g._update_enemies(); check("crush: 70px away on the same level: defeated", not e.alive)
e = crush_setup(130, 0); g._update_enemies(); check("crush: 130px away on the same level: NOT defeated", e.alive)
def crush_below(dy):                      # Mario stands in the air, the enemy walks on the ground `dy` px below his feet-line
    m = start(); no_enemies(); m.invincibility_timer = 9999; m.rect.x = 1000; m.rect.bottom = Config.ground_y - 30 - dy
    m.velocity_y = 0; m.power = "crush"; m.power_timer = 180
    enemy = Mushroom(m.rect.x + 10, Config.ground_y - 30, 120); g.level[1].append(enemy); g._update_enemies(); return enemy
check("crush: an enemy about one body below Mario (feet 12px above the ground): defeated", not crush_below(12).alive)
check("crush: an enemy 100px lower than Mario: NOT defeated", crush_below(100).alive)
# the power starts by touching a Lucky Block (g._give_power) and the very same frame's enemy update applies it
for dx, dy in ((150, 0), (40, -250), (40, 0), (70, 40)):
    a = crush_setup(dx, dy, power=False)
    block = type("B", (), {"reward": "crush", "rect": pygame.Rect(0, 0, 32, 32)})()
    g._give_power(block); g._update_enemies(); at_start = not a.alive
    b = crush_setup(dx, dy, power=True); g._update_enemies(); during = not b.alive
    check(f"crush: enemy at dx={dx}, dy={dy}: same result when the power starts ({at_start}) and while it lasts ({during})", at_start == during)

# ---- C. BOSS: fixed fight zone, never through pipes or obstacles (all five boss levels) ----
for number in (10, 20, 30, 40, 50):
    m = start(level=number); no_enemies(); boss = g.level[5]
    last_pipe = max(pipe.shaft.right + Pipe.lip_extension for pipe in g.level[2])
    intruders = [r for r in g.level[0][1:] if r.right > boss.arena_left] + [b.rect for b in g.level[4] if b.rect.right > boss.arena_left] + [e.rect for e in g.level[1] if e.rect.right > boss.arena_left]
    check(f"boss level {number}: the fight zone has no floating platform, block or enemy in it (nothing to hide on)", not intruders, len(intruders))
    check(f"boss level {number}: every pipe lies before the fight zone (last pipe ends at {last_pipe}, zone starts at {boss.arena_left})", last_pipe < boss.arena_left)
    m.invincibility_timer = 10 ** 7; outside = inside_solid = 0; lowest = 10 ** 9
    for _ in range(1800):
        m.rect.x = 100; m.rect.bottom = Config.ground_y; m.velocity_x = m.velocity_y = 0
        g._play_frame()
        lowest = min(lowest, boss.rect.left)
        if boss.rect.left < boss.arena_left or boss.rect.right > Config.level_width: outside += 1
        if boss.rect.collidelist(g.solids) != -1: inside_solid += 1
    check(f"boss level {number}: with Mario far away the boss never leaves its zone (lowest x {lowest}, zone starts at {boss.arena_left})", outside == 0 and lowest >= boss.arena_left, outside)
    check(f"boss level {number}: ...never overlaps a pipe, block or platform", inside_solid == 0, inside_solid)
    check(f"boss level {number}: ...but it really chases Mario to the edge of its zone", abs(boss.rect.left - boss.arena_left) <= boss.speed, boss.rect.left)
    out2 = 0
    for index in range(1200):
        m.rect.x = 4600 if (index // 200) % 2 else 3000; m.rect.bottom = Config.ground_y; m.velocity_x = m.velocity_y = 0
        g._play_frame()
        if boss.rect.left < boss.arena_left or boss.rect.right > Config.level_width: out2 += 1
    check(f"boss level {number}: Mario running from one side to the other: the boss stays in the zone", out2 == 0)
m = start(level=10); no_enemies(); boss = g.level[5]
pipe = Pipe(4000, Config.ground_y); g.level[2].append(pipe); g.solids.extend((pipe.shaft, pipe.lip_center))
m.invincibility_timer = 10 ** 7; through = 0
for _ in range(900):
    m.rect.x = 3950; m.rect.bottom = Config.ground_y; m.velocity_x = m.velocity_y = 0
    g._play_frame()
    if boss.rect.left < pipe.shaft.right - 1 and boss.rect.right > pipe.shaft.left: through += 1
check("boss: a pipe in its way stops it (it cannot pass through)", through == 0 and boss.rect.left >= pipe.shaft.right - 1, f"x={boss.rect.left} through={through}")

# ---- C2. a successful stomp on the boss must not cost a life (a fast fall sinks Mario into the boss) ----
m = start(level=10); no_enemies(); boss = g.level[5]; boss.hurt = 0; boss.attack_cooldown = 9999
m.invincibility_timer = 0; hp0 = boss.health
m.rect.centerx = boss.rect.centerx; m.rect.bottom = boss.rect.top - 5; m.velocity_y = 18; m.subpixel_y = 0; m.on_ground = False   # falls 18px: sinks 13px into the boss
lives0 = m.lives
for _ in range(4):
    g.update_play()
check("boss stomp: a fast fall onto the boss's head hurts the boss by exactly 1 HP", boss.health == hp0 - 1, f"hp {hp0} -> {boss.health}")
check("boss stomp: ...and Mario keeps his life AND all his hearts (a good stomp must cost nothing: the old bug counted it as a side hit)", m.lives == lives0 and g.state == "playing" and m.boss_hits == 0, f"lives={m.lives} hits={m.boss_hits}")
check("boss stomp: ...and he bounces up off the boss (is above it, not inside it)", m.rect.bottom <= boss.rect.top, f"bottom={m.rect.bottom} top={boss.rect.top} vy={m.velocity_y}")

# ---- D. switching heroes: all four, nobody shown twice ----
def looks():
    return sorted([g.mario.active_character] + [c.appearance for c in g.companions])
m = start(level=25); order = []
for _ in range(5): g._cycle_character(); order.append(g.mario.active_character)
check("heroes: with all four unlocked T cycles Mario > Luigi > Princess > Yoshi > Mario > Luigi", ">".join(order) == "luigi>princess>yoshi>mario>luigi", ">".join(order))
m = start(level=25); bad = 0
for _ in range(9):
    g._cycle_character()
    if looks() != ["luigi", "mario", "princess", "yoshi"]: bad += 1
check("heroes: after every switch each of the four characters is shown exactly once (no twin on screen)", bad == 0, looks())
m = start(level=15); order = []
for _ in range(4): g._cycle_character(); order.append(g.mario.active_character)
check("heroes: levels 11-20 have three heroes", ">".join(order) == "luigi>princess>mario>luigi", ">".join(order))
m = start(level=5); g._cycle_character(); check("heroes: in chapter 1 T does nothing", m.active_character == "mario")
m = start(level=25); g.state = "playing"
down(pygame.K_t); frame(); up(pygame.K_t)
check("heroes: the real T key switches the hero", m.active_character == "luigi")
calls = {}
def spy(module, name):
    original = getattr(module, name)
    def wrapper(*args, **kwargs): calls[name] = calls.get(name, 0) + 1; return original(*args, **kwargs)
    setattr(module, name, wrapper); return lambda: setattr(module, name, original)
undo = [spy(player_module, "draw_luigi"), spy(player_module, "draw_princess"), spy(player_module, "draw_yoshi"),
        spy(companions_module, "draw_luigi"), spy(companions_module, "draw_princess"), spy(companions_module, "draw_yoshi")]
original_body = Mario._draw_body
def body_spy(self, *a, **k): calls["mario_body"] = calls.get("mario_body", 0) + 1; return original_body(self, *a, **k)
Mario._draw_body = body_spy
m = start(level=25); m.invincibility_timer = 0
for kind, expected in (("mario", "mario_body"), ("luigi", "draw_luigi"), ("princess", "draw_princess"), ("yoshi", "draw_yoshi")):
    calls.clear(); m.active_character = kind; m.draw(g.screen, 0)
    check(f"heroes: playing as {kind} draws the {kind} sprite", calls.get(expected, 0) >= 1, dict(calls))
calls.clear(); luigi = next(c for c in g.companions if c.kind == "luigi"); luigi.appearance = "mario"; luigi.draw(g.screen, 0)
check("heroes: a team member that took Mario's place is drawn as Mario (not as Luigi)", calls.get("mario_body") == 1 and "draw_luigi" not in calls, dict(calls))
Mario._draw_body = original_body
for fn in undo: fn()
m = start(level=25)
for kind in ("mario", "luigi", "princess", "yoshi"): m.active_character = kind; g.draw_play()
check("heroes: the whole play screen draws with each hero, no error", True)

# ---- E. saving: the message must tell the truth ----
saved_dir, saved_path = Config.save_directory, Config.save_file_path
def break_saving():
    open("blocked", "w").write("a file where the save folder should be")
    Config.save_directory = "blocked"; Config.save_file_path = os.path.join("blocked", "save.json")
def fix_saving():
    Config.save_directory, Config.save_file_path = saved_dir, saved_path
m = start(); no_enemies(); g.state = "paused"; break_saving()
down(pygame.K_q); g.handle_pause()
check("save: when the save FAILS, Q does not say SAVED and does not leave the game", g.state == "paused" and g.falling is None, g.state)
check("save: ...a clear error is shown on the pause screen", "FAILED" in g.pause_message and "NOT saved" in g.pause_message, g.pause_message)
g.draw_pause(); check("save: the pause screen draws with the error", True)
fix_saving(); up(pygame.K_q); down(pygame.K_q); g.handle_pause()
check("save: trying again after the problem is gone works (SAVED, back to the menu)", g.state == "falling_text" and g.fall_next_state == "menu" and has_save() and g.pause_message == "")
up(pygame.K_q)
# a write that "succeeds" but leaves nothing behind
real_replace = save_system.os.replace; save_system.os.replace = lambda a, b: None
if os.path.exists(Config.save_file_path): os.remove(Config.save_file_path)
check("save: a write that leaves no file behind is reported as a failure", save_game(1, 3, None, None, 0) is False)
save_system.os.replace = real_replace
check("save: save_game returns True for a real save", save_game(2, 3, None, None, 0) is True and load_game()["level"] == 2)
m = start(); no_enemies(); break_saving(); m.rect.x = g.level[3][0].world_x - 10; m.rect.bottom = Config.ground_y; g._update_checkpoints()
check("save: an autosave that fails at a checkpoint says so (not just CHECKPOINT!)", g.flash and "SAVE FAILED" in g.flash[0] and "✔" not in g.flash[0], g.flash); fix_saving()
m = start(); no_enemies(); m.rect.x = g.level[3][0].world_x - 10; m.rect.bottom = Config.ground_y; g._update_checkpoints()
check("save: ...and a successful one still says CHECKPOINT", g.flash and "CHECKPOINT!" in g.flash[0] and "FAILED" not in g.flash[0], g.flash)
m = start(); break_saving(); g._next_level()
check("save: a new level that could not be saved says so", g.flash and "SAVE FAILED" in g.flash[0] and g.current_level == 2, g.flash); fix_saving()
m = start(); g._next_level(); check("save: ...and a normal new level shows no error", not (g.flash and "FAILED" in g.flash[0]) and load_game()["level"] == 2)
save_game(7, 2, None, None, 0); break_saving(); g.new_game()
check("save: New Game when saving is impossible warns the player", g.flash and "NOT be saved" in g.flash[0], g.flash); fix_saving()


# =====================================================================================================
# DEBUG MODE: password from .env, any level, leave, and the real save is never touched
# =====================================================================================================
import debug_mode
def press_key(key, char=""): pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=char, mod=0))
def type_text(text):
    for ch in text: press_key(ord(ch) if ch.isalnum() else 0, ch); g.handle_debug_password()
def to_menu():
    g.state = "menu"; g._build_menu()
env_dir = tempfile.mkdtemp(); env_path = os.path.join(env_dir, "test.env")
def write_env(text):
    open(env_path, "w").write(text); os.environ["MARIO_ENV_FILE"] = env_path

# the .env reader
write_env("# a comment\n\nDEBUG_PASSWORD=8830\nOTHER = ' spaced value '\nBAD LINE\n")
check("debug .env: the password is read", debug_mode.debug_password() == "8830")
check("debug .env: quotes and spaces are handled", debug_mode.read_env_file(env_path)["OTHER"] == " spaced value ")
write_env('DEBUG_PASSWORD="quoted pw"\n'); check("debug .env: a quoted password works", debug_mode.debug_password() == "quoted pw")
write_env("DEBUG_PASSWORD=\n"); check("debug .env: an empty password means debug is off", debug_mode.debug_password() is None)
write_env("DEBUG_PASSWORD=change_me\n"); check("debug .env: the example value 'change_me' means debug is off", debug_mode.debug_password() is None)
os.environ["MARIO_ENV_FILE"] = os.path.join(env_dir, "missing.env"); check("debug .env: no file means debug is off", debug_mode.debug_password() is None)
check("debug .env: with debug off no password is ever correct (not even an empty one)", not debug_mode.password_is_correct("") and not debug_mode.password_is_correct("8830"))
to_menu(); check("debug: without a .env there is no Debug option in the menu", "Debug" not in g.menu_options, g.menu_options)

# opening it
write_env("DEBUG_PASSWORD=8830\n")
save_game(7, 2, None, "fly", 100)
real_save_text = open(save_game.__globals__["Config"].save_file_path).read()
to_menu(); check("debug: with a .env the menu has Debug (before Quit)", g.menu_options[-2:] == ["Debug", "Quit"], g.menu_options)
g.selected_index = g.menu_options.index("Debug"); press_key(pygame.K_RETURN); g.handle_menu()
check("debug: choosing Debug asks for the password", g.state == "debug_password")
for bad in ("", "1234", "8831", "88300", "883", "8830 ", "abcd"):
    g.debug_input = ""; type_text(bad); press_key(pygame.K_RETURN); g.handle_debug_password()
    check(f"debug: password {bad!r} is refused", g.state == "debug_password" and g.debug_message == "WRONG PASSWORD" and g.debug_input == "")
g.draw_debug_password(); check("debug: the password screen draws", True)
type_text("88"); press_key(pygame.K_BACKSPACE); g.handle_debug_password(); check("debug: Backspace removes a typed character", g.debug_input == "8")
g.debug_input = ""; press_key(pygame.K_LEFT); press_key(pygame.K_RIGHT); g.handle_debug_password(); check("debug: arrow keys in the password box do not open the picker", g.state == "debug_password")
g.debug_input = ""; type_text("8830"); check("debug: the box holds what was typed (shown as stars, never as text)", g.debug_input == "8830")
press_key(pygame.K_RETURN); g.handle_debug_password(); check("debug: the right password (8830) opens the level picker", g.state == "debug_levels" and g.debug_input == "")
g.draw_debug_levels(); check("debug: the level picker draws", True)

# the picker
g.debug_pick = 1; press_key(pygame.K_RIGHT); g.handle_debug_levels(); check("debug: right = +1", g.debug_pick == 2)
press_key(pygame.K_DOWN); g.handle_debug_levels(); check("debug: down = +10", g.debug_pick == 12)
press_key(pygame.K_UP); press_key(pygame.K_LEFT); g.handle_debug_levels(); check("debug: up = -10, left = -1", g.debug_pick == 1)
press_key(pygame.K_LEFT); g.handle_debug_levels(); check("debug: it stops at level 1", g.debug_pick == 1)
g.debug_pick = 45
for k in (pygame.K_DOWN, pygame.K_DOWN, pygame.K_RIGHT, pygame.K_RIGHT): press_key(k)
g.handle_debug_levels(); check("debug: it stops at level 50", g.debug_pick == 50)
press_key(pygame.K_2, "2"); press_key(pygame.K_7, "7"); g.handle_debug_levels(); check("debug: typing 2 then 7 picks level 27", g.debug_pick == 27, g.debug_pick)
press_key(pygame.K_9, "9"); press_key(pygame.K_9, "9"); g.handle_debug_levels(); check("debug: typing 99 gives level 50", g.debug_pick == 50, g.debug_pick)
press_key(pygame.K_0, "0"); g.handle_debug_levels(); check("debug: digits keep the last two typed (99 then 0 = 90, capped to 50)", g.debug_pick == 50, g.debug_pick)
press_key(pygame.K_LEFT); press_key(pygame.K_0, "0"); g.handle_debug_levels(); check("debug: after an arrow key a lone 0 starts a new number and gives level 1", g.debug_pick == 1, g.debug_pick)

# every level can be started
started, bad_lives, bad_team = True, 0, 0
for number in range(1, 51):
    g.state = "debug_levels"; g.debug_pick = number; press_key(pygame.K_RETURN); g.handle_debug_levels()
    if not (g.state == "playing" and g.current_level == number and g.debug_active and g.checkpoint_x is None): started = False
    if g.mario.lives != 3: bad_lives += 1
    wanted = 0 if (number - 1) // 10 == 0 else 2 if (number - 1) // 10 == 1 else 3
    if len(g.companions) != wanted: bad_team += 1
check("debug: every level 1..50 can be started from the picker", started)
check("debug: ...with 3 lives each time", bad_lives == 0)
check("debug: ...and the right team for the chapter (none, Luigi + Princess, + Yoshi)", bad_team == 0)
g.debug_start(33); g.draw_play(); check("debug: the play screen draws with the DEBUG tag", True)
# leave
press_key(pygame.K_l); g.handle_play()
check("debug: L leaves the level and returns to the picker, keeping level 33 selected", g.state == "debug_levels" and g.debug_active and g.debug_pick == 33 and "LEFT LEVEL 33" in g.debug_message, g.state)
g.debug_start(33); g._pause(); press_key(pygame.K_q); g.handle_pause()
check("debug: in the pause menu Q leaves the level (and does not 'save')", g.state == "debug_levels" and g.falling is None)
g.debug_start(12); g._next_level(); check("debug: reaching the goal returns to the picker instead of the next level", g.state == "debug_levels" and "CLEARED" in g.debug_message and g.current_level == 12)
g.debug_start(12); g.mario.lives = 1; g._take_life(); check("debug: losing every life returns to the picker (no GAME OVER screen)", g.state == "debug_levels" and "GAME OVER" in g.debug_message and g.falling is None)
g.debug_start(50); g._next_level(); check("debug: finishing level 50 shows no ending, just the picker", g.state == "debug_levels")
# the real save is never touched
g.debug_start(20); m = g.mario; no_enemies(); m.rect.x = g.level[3][0].world_x - 10; m.rect.bottom = Config.ground_y; g._update_checkpoints()
check("debug: a checkpoint in debug mode does not touch the save", open(Config.save_file_path).read() == real_save_text)
check("debug: nothing written in debug mode (the save call says OK but stores nothing)", g._save_progress() is True and open(Config.save_file_path).read() == real_save_text)
g._debug_return(); press_key(pygame.K_ESCAPE); g.handle_debug_levels()
check("debug: ESC in the picker leaves debug mode to the main menu", g.state == "menu" and not g.debug_active and "Debug" in g.menu_options)
check("debug: the real save is exactly as before", open(Config.save_file_path).read() == real_save_text and load_game()["level"] == 7)
g.selected_index = g.menu_options.index("Continue"); press_key(pygame.K_RETURN); g.handle_menu()
check("debug: Continue after debug resumes the REAL save (level 7, 2 lives)", g.current_level == 7 and g.mario.lives == 2 and not g.debug_active)
g.state = "menu"; g._build_menu(); g.selected_index = g.menu_options.index("Debug"); press_key(pygame.K_RETURN); g.handle_menu(); press_key(pygame.K_ESCAPE); g.handle_debug_password()
check("debug: ESC in the password box goes back to the menu", g.state == "menu")
g.new_game(); check("debug: a new game is never a debug game", not g.debug_active)
os.environ["MARIO_ENV_FILE"] = NO_ENV_FILE


# =====================================================================================================
# REPORTED BUGS (Python): lucky blocks, flying, boss hearts, Princess, team AI
# =====================================================================================================
from world_objects import LuckyBlock
held.clear()

# ---- L. Lucky blocks are items: Mario passes through them, they give the power once, and then they are gone ----
m = start(); no_enemies()
check("lucky block: no block is a solid (Mario can walk or jump into it)", all(s != b.rect for b in g.level[4] for s in g.solids))
g.level[4].clear(); block = LuckyBlock(400, Config.ground_y - 38, "crush"); g.level[4].append(block)
m.rect.x = 360; m.rect.bottom = Config.ground_y; held.add(pygame.K_RIGHT)
frame(4)
check("lucky block: walking into it gives the power", m.power == "crush" and block.used, f"power={m.power}")
check("lucky block: ...Mario is NOT stopped by it", m.rect.x > 372, f"x={m.rect.x}")
frame(12)
check("lucky block: ...he walks right through to the other side", m.rect.x > block.rect.right, f"x={m.rect.x}")
check("lucky block: ...and while its coin pops the block is still in the list", block in g.level[4])
frame(45)
check("lucky block: after the coin pop the block has DISAPPEARED", block not in g.level[4] and len(g.level[4]) == 0, len(g.level[4]))
check("lucky block: ...the power stays", m.power == "crush" and m.power_timer > 0)
held.clear()
m = start(); no_enemies(); g.level[4].clear(); m.rect.x = 600
block = LuckyBlock(m.rect.x, Config.ground_y - 100, "jump"); g.level[4].append(block)
top = m.rect.y; down(pygame.K_SPACE)
for _ in range(40):
    frame(); top = min(top, m.rect.y)
up(pygame.K_SPACE)
check("lucky block: jumping into it from below does not bump Mario's head (his jump rises ABOVE the block)", top < block.rect.y - 20, f"highest y={top} block y={block.rect.y}")
check("lucky block: ...he got the power", m.power == "jump")
g.level[4].append(LuckyBlock(m.rect.x, m.rect.y, "fly"))
frame(1); check("lucky block: a second block replaces the power", m.power == "fly")
frame(45); check("lucky block: ...no used block is left behind", all(not b.used for b in g.level[4]))
def box_pixels(block):
    canvas = pygame.Surface((200, 200), pygame.SRCALPHA); block.rect.topleft = (80, 80); block.draw(canvas, 0, g.font_small)
    return sum(1 for x in range(80, 112) for y in range(80, 112) if canvas.get_at((x, y))[:3] == (255, 180, 30))
fresh_block = LuckyBlock(300, 300, "fly"); blk = LuckyBlock(300, 300, "fly"); blk.try_hit(); blk.coin_pop_timer = 10; g.level[4].append(blk)
check("lucky block: a block that is waiting IS drawn as an orange box", box_pixels(fresh_block) > 200, box_pixels(fresh_block))
check("lucky block: a block that was just taken is NOT drawn as a box any more (only the coin)", box_pixels(blk) == 0, box_pixels(blk))
g.draw_play(); check("lucky block: the whole screen draws with a block that was just taken", True)
for level_number in (1, 2, 3, 12, 25, 50):
    mm = start(level_number); n0 = len(g.level[4])
    check(f"lucky block: level {level_number} has its blocks and none is solid", n0 >= 1 and all(s != b.rect for b in g.level[4] for s in g.solids), n0)

# ---- F. flying ----
def fly_setup():
    mm = start(); no_enemies(); held.clear(); mm.power = "fly"; mm.power_timer = Config.power_duration_frames; mm.rect.x = 50; return mm
m = fly_setup(); y0 = m.rect.y; held.add(pygame.K_UP); frame(30)
check("fly: holding UP lifts Mario at the fly speed (it did not lift him at all)", abs((y0 - m.rect.y) - 30 * Config.fly_speed) <= 6, f"rose {y0 - m.rect.y}px")
held.clear(); y1 = m.rect.y; frame(20)
check("fly: letting go makes him hover (no falling)", abs(m.rect.y - y1) <= 1 and m.velocity_y == 0, f"{y1}->{m.rect.y}")
held.add(pygame.K_DOWN); frame(10); held.clear()
check("fly: holding DOWN lowers him", m.rect.y - y1 >= 8 * Config.fly_speed, f"{y1}->{m.rect.y}")
for key_name, key in (("SPACE", pygame.K_SPACE), ("W", pygame.K_w)):
    mm = fly_setup(); y = mm.rect.y; held.add(key); frame(10); held.clear()
    check(f"fly: {key_name} lifts him too", y - mm.rect.y >= 8 * Config.fly_speed, f"rose {y - mm.rect.y}")
m = fly_setup(); m.rect.x = 820; held.update({pygame.K_RIGHT, pygame.K_UP}); frame(25); held.discard(pygame.K_UP); frame(40); held.clear()
pipe_end = g.level[2][0].shaft.right
check("fly: he can fly over the first pipe", m.rect.x > pipe_end and m.lives == 3 and g.state == "playing", f"x={m.rect.x} pipe ends {pipe_end}")
m = fly_setup(); m.rect.x = 50; m.power_timer = 30; held.add(pygame.K_UP); frame(29); check("fly: the power is still on in its last frames", m.power == "fly")
frame(6); check("fly: when the 3 seconds are over the power ends", m.power is None)
y_top = m.rect.y; frame(20); held.clear()
check("fly: ...and then gravity pulls him down again (holding UP no longer lifts him)", m.rect.y > y_top, f"{y_top}->{m.rect.y}")
m = fly_setup(); plat = next(p for p in g.level[0][1:] if p.width >= 60); m.rect.centerx = plat.centerx; m.rect.top = plat.bottom + 40
held.add(pygame.K_UP); frame(30); held.clear()
check("fly: a platform above stops him (he cannot fly through solid ground)", m.rect.top >= plat.bottom, f"top={m.rect.top} platform bottom={plat.bottom}")

# ---- H. boss fight: 10 hearts like the HTML game ----
m, boss = boss_next_to_mario(5); lives = m.lives
check("boss hearts: Mario starts a boss fight with 0 hits taken", m.boss_hits == 0)
for hit in range(1, Config.boss_hit_limit):
    m.invincibility_timer = 0; lost = g._update_boss()
    if lost or m.lives != lives or m.boss_hits != hit: break
check(f"boss hearts: {Config.boss_hit_limit - 1} touches cost hearts but NOT a life", m.boss_hits == Config.boss_hit_limit - 1 and m.lives == lives and g.state == "playing", f"hits={m.boss_hits} lives={m.lives}")
check("boss hearts: after a hit Mario is protected for a second", m.invincibility_timer == Config.boss_hit_invincibility)
before = m.boss_hits; g._update_boss(); check("boss hearts: touching again while protected takes nothing", m.boss_hits == before)
m.invincibility_timer = 0; lost = g._update_boss()
check("boss hearts: the LAST heart costs a life", lost and m.lives == lives - 1, f"lost={lost} lives={m.lives}")
check("boss hearts: ...and the next life starts with all hearts again", g.mario.boss_hits == 0, g.mario.boss_hits)
m, boss = boss_next_to_mario(5); m.invincibility_timer = 0
boss.projectiles.append({"x": float(m.rect.centerx), "y": float(m.rect.centery), "velocity_x": 0.0, "velocity_y": 0.0, "life": 99, "variant": "normal"})
lost = g._update_boss(); check("boss hearts: a shell hit also takes just one heart", not lost and m.boss_hits == 1 and not boss.projectiles, f"hits={m.boss_hits}")
m, boss = boss_next_to_mario(5); m.rect.bottom = boss.rect.top + 6; m.rect.centerx = boss.rect.centerx; m.velocity_y = 6
g._update_boss(); check("boss hearts: a good stomp takes no heart", m.boss_hits == 0 and boss.health == 4)
m, boss = boss_next_to_mario(5); m.boss_hits = 0; g.draw_play(); full = g.screen.copy()
m.boss_hits = 6; g.draw_play(); some = g.screen.copy()
row = pygame.Rect(Config.screen_width // 2 - 110, Config.screen_height - 52, 220, 30)
check("boss hearts: the screen shows the hearts and loses them as Mario is hit", pygame.image.tostring(full.subsurface(row), "RGB") != pygame.image.tostring(some.subsurface(row), "RGB"))
m, boss = boss_next_to_mario(5); m.boss_hits = 4; g._lose_life()
check("boss hearts: losing a life through any route restores the hearts", g.mario.boss_hits == 0, g.mario.boss_hits)

# ---- P. the Princess stands ON the ground (she was drawn 25px into it) ----
def lowest_row(surface):
    mask = pygame.mask.from_surface(surface)
    rows = [y for y in range(surface.get_height()) if any(mask.get_at((x, y)) for x in range(0, surface.get_width(), 2))]
    return max(rows) if rows else -1
for kind in ("luigi", "princess", "yoshi"):
    mm = start(level=25); comp = next(c for c in g.companions if c.kind == kind)
    canvas = pygame.Surface((300, 300), pygame.SRCALPHA); comp.rect.topleft = (120, 150); comp.frame = 0; comp.draw(canvas, 0)
    bottom = lowest_row(canvas)
    check(f"{kind}: the feet are on the ground line (drawn bottom {bottom}, body bottom {comp.rect.bottom})", comp.rect.bottom - 3 <= bottom <= comp.rect.bottom + 2, f"bottom row {bottom} vs {comp.rect.bottom}")
sunk = []
real_princess = player_module.draw_princess
player_module.draw_princess = lambda surface, x, y, frame=0: sunk.append(y)
mm = start(level=25); mm.active_character = "princess"; mm.invincibility_timer = 0; mm.draw(g.screen, 0)
player_module.draw_princess = real_princess
check("princess as the hero: she is drawn on Mario's rectangle, not 25px below it", sunk and sunk[0] == mm.rect.y - __import__("sprites").PRINCESS_SINK, sunk)

# ---- A. team AI: the team gets over pipes and keeps up ----
def team_follow(level_number, frames=4200):
    start(level=level_number); no_enemies()
    mm = g.mario; mm.invincibility_timer = 10 ** 7
    if g.level[5]: g.level[5].alive = False
    pipes = [p.shaft.left for p in g.level[2]]; fell = 0
    for _ in range(frames):
        if mm.rect.x < 4300:
            mm.velocity_x = Config.player_speed; mm.facing = 1
            if mm.on_ground and any(0 < p - mm.rect.right < 30 for p in pipes): mm.press_jump()
        else: mm.velocity_x = 0
        g.update_play()
        if g.state != "playing": break
        fell += sum(1 for c in g.companions if c.rect.y > Config.screen_height + 10)
    return [mm.rect.x - c.rect.x for c in g.companions], fell, g.state
for level_number in (11, 21, 31, 41, 50):
    lags, fell, state = team_follow(level_number)
    check(f"team AI: level {level_number}: every team member gets past all the pipes and catches up with Mario", state == "playing" and fell == 0 and all(l < 260 for l in lags), f"lags={lags} fell={fell} state={state}")
start(level=11); no_enemies(); mm = g.mario; mm.invincibility_timer = 10 ** 7; pipe = g.level[2][0]
mm.rect.x = pipe.shaft.right + 200; mm.rect.bottom = Config.ground_y
for c in g.companions: c.rect.x = pipe.shaft.left - 200 + 30 * g.companions.index(c); c.rect.bottom = Config.ground_y
trail = []
for _ in range(500):
    mm.velocity_x = 0; g.update_play(); trail.append(g.companions[0].rect.x)
check("team AI: a team member in front of a pipe jumps OVER it (it used to hop on the spot in front of it for ever)", all(c.rect.left > pipe.shaft.right for c in g.companions), [c.rect.x for c in g.companions])
check("team AI: ...and none of them is stuck on top of it", not any(c._on_pipe_rim(g.level[2]) for c in g.companions))
check("team AI: ...they did not just hop in place (x kept increasing)", trail[-1] - trail[0] > 250, trail[-1] - trail[0])
held.clear()

fails = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
for n in fails: print("  FAILED:", n)
print("RESULT:", "FAIL" if fails else "PASS")
sys.exit(1 if fails else 0)          # non-zero exit code = at least one check failed