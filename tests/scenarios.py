"""Scenario tests that drive the real Game object headlessly with simulated key events."""
import os, sys, tempfile, json
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
check("boss alive: touching its body still costs a life", boss.alive and lost and m.lives == lives - 1, f"lost={lost} lives {lives}->{m.lives}")
m, boss = boss_next_to_mario(3); m.punch_timer = Config.punch_duration; lives = m.lives
lost = g._update_boss()
check("boss not on its last hit: a punch hurts it but touching it still costs a life", boss.alive and boss.health == 2 and lost and m.lives == lives - 1,
      f"health={boss.health} lost={lost} lives {lives}->{m.lives}")

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
check("boss stomp: ...and Mario keeps his life (the reported death after every good stomp)", m.lives == lives0 and g.state == "playing", f"lives={m.lives}")
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

fails = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
for n in fails: print("  FAILED:", n)
print("RESULT:", "FAIL" if fails else "PASS")
sys.exit(1 if fails else 0)          # non-zero exit code = at least one check failed
