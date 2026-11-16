"""A bot plays EVERY level through the real Game object, under the game's own rules.

Unlike static_levels.py (are the platforms in sensible places?) and bot_levels.py (can the physics
reach the goal with no enemies?), this test uses the whole game:

  * real enemies that cost a life when they touch Mario from the side,
  * the boss, its shells, and the goal that stays locked until the boss is dead,
  * lives (3 per run), respawning at checkpoints, game over,
  * the level counter, the save file and the ending after level 50.

Two kinds of run are made:

  1. Every level separately. Each one is started like a player would start it (fresh lives, no
     power-up) and the bot has to reach the next level (or the ending, after level 50) without a
     GAME OVER.
  2. ONE continuous run. The game is started once, at level 1, and the bot plays on until the game
     itself has brought it to level 50, then defeats the boss of level 50 and the game enters its
     ending (walk, hearts, credits; run up to the final screen). There is no new_game() and no
     _load_level() in between (a guard fails the test if the game is restarted). The level counter,
     the banners and chapter cutscenes between levels, the save file and the lives are all handled by
     the game, as in a real session. The lives rule that the test expects is written down in
     lives_on_arrival(), so it is checked at every level change instead of being faked.

The continuous run only happens when the whole range (1 to 50) is tested.

Usage:  python full_playthrough.py <path to the mario_game source folder> [first_level [last_level]]
Exit code: 0 when everything passed, 1 when any level (or the continuous run) failed.
"""
import math
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.abspath(sys.argv[1]))  # absolute: the next line changes the folder
os.chdir(tempfile.mkdtemp())  # saves/ goes to a throw-away folder

import pygame

from settings import Config
from game import Game
from save_system import load_game

MAX_FRAMES_PER_LEVEL = 9000  # 2.5 minutes of play: far more than any level needs

# ---- fake keyboard, the same idea as in scenarios.py ----
held = set()


class Keys:
    def __getitem__(self, key):
        return key in held


pygame.key.get_pressed = lambda: Keys()


def press(key):
    """A key goes down (and stays held until release is called)."""
    held.add(key)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))


def release(key):
    held.discard(key)
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key))


def tap(key):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key))


game = Game()


class Bot:
    """Plays like a simple but sensible human: run right, jump what is in the way, punch enemies."""

    def __init__(self, game):
        self.game = game
        self.jump_key_down = False

    # --- what the bot "sees" ---
    def _blocked_ahead(self, distance):
        mario = self.game.mario
        probe = pygame.Rect(mario.rect.right + 1, mario.rect.y + 2, distance, mario.rect.h - 4)
        return probe.collidelist(self.game.solids) != -1

    def _nearest_enemy_ahead(self):
        mario = self.game.mario
        nearest = None
        for enemy in self.game.level[1]:
            if not enemy.alive or enemy.squish:
                continue
            same_height = enemy.rect.bottom > mario.rect.top and enemy.rect.top < mario.rect.bottom
            gap = enemy.rect.left - mario.rect.right
            if same_height and -10 <= gap <= 140 and (nearest is None or gap < nearest[0]):
                nearest = (gap, enemy)
        return nearest

    def _shell_incoming(self):
        boss = self.game.level[5]
        if not (boss and boss.alive):
            return False
        mario = self.game.mario
        for shell in boss.projectiles:
            if abs(shell["x"] - mario.rect.centerx) < 70 and abs(shell["y"] - mario.rect.centery) < 60:
                return True
        return False

    def _predict_hit(self, jump, direction, delay=0, frames=90):
        """Would a boss shell hit Mario within the next `frames` frames if he stood (jump=False) or jumped now
        (jump=True) while walking in `direction`? Uses the game's own numbers: shells fly and fall as in
        Turtle.update, Mario rises and falls as in Mario._apply_jump_and_gravity. With `delay` Mario first stands
        still for that many frames and only then jumps."""
        boss = self.game.level[5]
        if not (boss and boss.alive):
            return False
        mario = self.game.mario
        solids = self.game.solids
        x, y = float(mario.rect.x), float(mario.rect.y)
        vy = 0.0
        airborne = False
        held, held_frames = False, 0         # the jump key is held (full rise) for Config.jump_hold_frames, then the rise fades
        shells = [[s["x"], s["y"], s["velocity_x"], s["velocity_y"], s["life"]] for s in boss.projectiles]
        for step in range(frames):
            if jump and step == delay:           # the jump starts now (the game applies gravity in the same frame)
                vy, airborne, held, held_frames = Config.player_jump_speed, True, True, 0
            if step >= delay or not jump:
                x += direction * Config.player_speed
            if airborne:
                if held:
                    held_frames += 1
                    if held_frames > Config.jump_hold_frames:
                        held = False
                elif vy < 0:
                    vy *= Config.jump_release_damping
                falling = vy > 0
                vy += Config.gravity * (Config.fall_gravity_multiplier if falling else 1.0)
                y += vy
                hit_index = pygame.Rect(int(x), int(y), mario.rect.w, mario.rect.h).collidelist(solids)
                if hit_index != -1:                      # a platform above stops the rise, the ground / a platform below lands him
                    solid = solids[hit_index]
                    if vy > 0:
                        y, airborne = float(solid.top - mario.rect.h), False
                    else:
                        y = float(solid.bottom)
                    vy = 0.0
            mario_box = pygame.Rect(int(x), int(y), mario.rect.w, mario.rect.h)
            # the boss fires when its cooldown is used up (then every 90 frames), aiming at where Mario is by then
            since_first = step - boss.attack_cooldown
            if since_first >= 0 and since_first % 91 == 0 and abs(x - boss.rect.x) < 520:
                origin_x, origin_y = boss.rect.centerx, boss.rect.y + 25
                delta_x, delta_y = x - origin_x, Config.ground_y - 30 - origin_y
                distance = max(1.0, math.hypot(delta_x, delta_y))
                shells.append([float(origin_x), float(origin_y), delta_x / distance * 7, delta_y / distance * 7 - 4, 120])
            for shell in shells[:]:
                shell[0] += shell[2]; shell[1] += shell[3]; shell[3] += 0.3; shell[4] -= 1
                if shell[4] <= 0 or shell[1] > Config.ground_y:
                    shells.remove(shell); continue
                half = Config.boss_shell_size // 2
                if mario_box.colliderect(pygame.Rect(int(shell[0] - half), int(shell[1] - half), Config.boss_shell_size, Config.boss_shell_size)):
                    return True
            # (the game checks the shells first, then the boss's body, so the same order here)
            if mario_box.colliderect(boss.rect):
                # landing on its head (falling, and above its top a frame ago) is a stomp = success; touching it any other way costs a life
                came_from_above = vy > 0 and mario_box.bottom - vy <= boss.rect.top + Config.stomp_tolerance_boss
                return not came_from_above
        return False

    # --- what the bot does in one frame ---
    def act(self):
        game = self.game
        mario = game.mario
        direction = 1  # +1 run right, -1 run left, 0 stand still
        want_jump = False
        want_punch = False

        boss = game.level[5]
        boss_alive = bool(boss and boss.alive)
        boss_near = boss_alive and boss.rect.left - mario.rect.right < 220

        enemy = self._nearest_enemy_ahead()
        if enemy is not None:
            gap, _ = enemy
            if gap <= 22:
                want_punch = True

        if self._blocked_ahead(8) and mario.on_ground:
            want_jump = True
        elif self._blocked_ahead(8) and not mario.on_ground and mario.velocity_y > 0 and mario.jumps_left == 1:
            want_jump = True  # second jump to clear a tall pipe

        if boss_near:
            # Boss fight, the way a player does it. A boss that waits in its fight zone does not run at Mario, so:
            #  * walk up to it on the ground and jump from the right distance to land on its head, then keep
            #    bouncing on its head (steering over its middle);
            #  * watch the shells: when one would hit a Mario who stands still, jump; when one would hit a Mario who
            #    is about to jump, wait. (The old boss ran at Mario and this worked by luck; it never dodged.)
            offset = boss.rect.centerx - mario.rect.centerx
            gap = boss.rect.left - mario.rect.right
            steer = 1 if offset > 12 else -1 if offset < -12 else 0
            if mario.on_ground:
                if gap > 120:
                    direction, want_jump = 1, self._blocked_ahead(8)
                elif gap >= 45:
                    # in the jump window: pick the first moment (now, or after waiting a few frames) at which the jump
                    # is predicted to be safe from the shells; if there is none, jump anyway
                    direction, want_jump = 1, True
                    for wait in range(0, 91, 3):
                        if not self._predict_hit(True, 1, wait):
                            want_jump = (wait == 0)
                            if not want_jump:
                                direction = 0
                            break
                elif gap >= -10:
                    direction, want_jump = -1, False          # too close to jump onto it: back off a little
                else:
                    direction, want_jump = steer, True
                if gap > 120 or gap < 45:
                    stay_is_hit = self._predict_hit(False, 0)          # "stay" = stand still where he is
                    jump_is_hit = self._predict_hit(True, direction)
                    if want_jump and jump_is_hit and not stay_is_hit:
                        want_jump = False
                    elif not want_jump and stay_is_hit and not jump_is_hit:
                        want_jump = True
            else:
                direction = steer
                rising = self.jump_key_down and mario.velocity_y < 0  # keep the key down: full-height jump
                second_jump = self._blocked_ahead(8) and mario.velocity_y > 0 and mario.jumps_left == 1
                want_jump = rising or second_jump

        # steering keys follow `direction`; the jump key is held while a jump is wanted
        for key, wanted in ((pygame.K_RIGHT, direction == 1), (pygame.K_LEFT, direction == -1)):
            if wanted and key not in held:
                press(key)
            elif not wanted and key in held:
                release(key)
        if want_jump and not self.jump_key_down:
            press(pygame.K_SPACE)
            self.jump_key_down = True
        elif not want_jump and self.jump_key_down:
            release(pygame.K_SPACE)
            self.jump_key_down = False
        if want_punch:
            tap(pygame.K_z)


def advance_to_playing():
    """Skip the falling-text banners and cutscenes between levels (not part of the play itself)."""
    for _ in range(2000):
        if game.state == "playing":
            return True
        if game.state == "falling_text":
            game.handle_falling()
        elif game.state == "cutscene":
            game.handle_cutscene()
        else:
            return False
    return False


def play_level(level_number):
    """Returns (ok, reason, frames, lives_lost)."""
    held.clear()
    pygame.event.clear()
    game.new_game()
    game.current_level = level_number
    game._load_level(level_number)  # a fresh start of that level, like arriving there from the previous one
    game.state = "playing"
    bot = Bot(game)
    lives_lost = 0
    lives_before = game.mario.lives

    for frame in range(MAX_FRAMES_PER_LEVEL):
        if game.state == "playing":
            bot.act()
            game.handle_play()
            if game.state == "playing":
                game.update_play()
        # Count lives while still on this level (the next level creates a new Mario with full lives).
        if game.current_level == level_number and game.state != "ending":
            lives_lost += max(0, lives_before - game.mario.lives)
            lives_before = game.mario.lives
        if game.state == "falling_text" and game.fall_next_state == "menu":
            return False, "GAME OVER (all lives lost)", frame, lives_lost
        if game.state == "ending":
            return True, "ending reached", frame, lives_lost
        if game.current_level == level_number + 1:
            return True, "reached the next level", frame, lives_lost
        if game.state in ("falling_text", "cutscene"):
            advance_to_playing()  # a life lost shows no banner, so this is only the level change
    return False, f"did not finish within {MAX_FRAMES_PER_LEVEL} frames (x={game.mario.rect.x})", MAX_FRAMES_PER_LEVEL, 0


def lives_on_arrival(lives_left_on_previous_level):
    """How many lives Mario must have when a new level starts, according to the game's own rules.

    Game._load_level builds a brand-new Mario for every level, and a new Mario has
    Config.starting_lives. So lives are NOT carried over from level to level: every level starts
    with a full set, and the number left on the previous level does not matter. Losing all of them
    inside one level is GAME OVER. If the game's rule changes, change it here, in this one place.
    """
    return Config.starting_lives


def ending_frame():
    """One frame of the ending states, with the same calls the main loop (Game.run) makes for them."""
    if game.state == "ending":                 # Mario walks to the princess, then the hearts scene
        game.handle_ending()
        game.update_ending()
        game.draw_ending()
    elif game.state == "falling_text":         # the "MADE BY ..." letters fall in between
        game.handle_falling()
        game.draw_falling()
    elif game.state == "ending_credits":       # the last screen: credits, then waiting for ENTER
        game.handle_ending()
        if game.falling:
            game.falling.update()
            game.fall_timer += 1
            if game.falling.finished and game.fall_timer > Config.credits_hold_frames:
                game.falling = None
        game.draw_ending_credits()


class Restarted(Exception):
    """Raised if the game starts a new game in the middle of the continuous run."""


def play_continuous(last_level=Config.max_levels):
    """Start the game ONCE, play from level 1 to the end of level `last_level`, and enter the ending screen.

    The test never calls new_game() again, never calls _load_level() and never sets
    game.current_level / mario.lives itself: the game moves from level to level on its own
    (Game._next_level). A guard turns any second new_game() into a failure. At every level change the
    test checks that the level counter went up by exactly one, that the lives follow lives_on_arrival()
    and that the save file matches the game. On the last level the bot has to defeat the boss; the goal
    then opens, the game enters its ending and the ending is run up to its final credits screen.
    Returns True when all of that happened.
    """
    held.clear()
    pygame.event.clear()
    game.new_game()  # the only start of this run: level 1, a brand-new Mario
    real_new_game = game.new_game

    def no_restart(*args, **kwargs):
        raise Restarted("new_game() was called again: the game was started over")
    game.new_game = no_restart  # from here on any restart is an error

    level = game.current_level
    arrival_lives = game.mario.lives
    total_frames = 0
    level_frames = 0
    bot = Bot(game)

    def fail(reason):
        print(f"FAIL continuous run, on level {level}: {reason}  (total frames={total_frames})")
        return False

    try:
        if level != 1 or game.state != "playing":
            return fail(f"new_game() did not start at level 1 (level={level}, state={game.state})")
        if arrival_lives != lives_on_arrival(None):
            return fail(f"level 1 starts with {arrival_lives} lives, the rules say {lives_on_arrival(None)}")

        # ---- level 1 -> last level, and on through the last level until the game itself ends ----
        while game.state != "ending":
            mario_of_this_level = game.mario  # the same object after the frame if the level did not change
            if game.state == "playing":
                bot.act()
                game.handle_play()
                if game.state == "playing":
                    game.update_play()
            level_frames += 1
            total_frames += 1

            if game.state == "falling_text" and game.fall_next_state == "menu":
                return fail(f"GAME OVER, all {arrival_lives} lives lost (frames on this level={level_frames})")
            if game.state == "ending":
                break
            if game.current_level == level:
                if level_frames >= MAX_FRAMES_PER_LEVEL:
                    boss = game.level[5]
                    return fail(f"did not finish the level within {MAX_FRAMES_PER_LEVEL} frames (state={game.state}, "
                                f"x={game.mario.rect.x}, boss alive={bool(boss and boss.alive)})")
                continue

            # ---- the game has moved on to another level by itself ----
            lives_left = mario_of_this_level.lives  # what the player had when walking into the goal
            if game.current_level != level + 1:
                return fail(f"the level counter went from {level} to {game.current_level}, expected {level + 1}")
            expected = lives_on_arrival(lives_left)
            if game.mario.lives != expected:
                return fail(f"level {game.current_level} starts with {game.mario.lives} lives, the rules say {expected} "
                            f"({lives_left} were left on level {level})")
            saved = load_game()  # what "Continue" would bring back right now
            if saved is None or saved["level"] != game.current_level or saved["lives"] != game.mario.lives:
                return fail(f"the save file ({saved}) does not match the game (level {game.current_level}, "
                            f"{game.mario.lives} lives): Continue would not give the same game")
            lost = arrival_lives - lives_left
            print(f"PASS level {level:2d} -> {game.current_level:2d}: frames={level_frames}, lives lost={lost}, "
                  f"left={lives_left}, level {game.current_level} starts with {game.mario.lives}")

            level = game.current_level
            arrival_lives = game.mario.lives
            level_frames = 0
            held.clear()  # the player lets go of the keys while the banner / cutscene is shown
            pygame.event.clear()
            bot = Bot(game)
            if not advance_to_playing():
                return fail(f"never got back to playing after the level change (state={game.state})")

        # ---- the game entered its ending: it may only happen by finishing the last level ----
        boss = game.level[5]
        if level != last_level or game.current_level != last_level:
            return fail(f"the ending came on level {game.current_level}, expected level {last_level}")
        if boss is None or boss.alive:
            return fail("the ending came while the boss of the last level was still alive")
        saved = load_game()
        if saved is None or saved["level"] != last_level:
            return fail(f"the save is not valid after the ending: {saved}")
        lives_left = game.mario.lives
        print(f"PASS level {level:2d}: boss defeated, the game entered its ending  (frames={level_frames}, "
              f"lives lost={arrival_lives - lives_left}, left={lives_left})")

        # ---- run the ending: walk, hearts, falling "MADE BY" letters, then the credits screen ----
        ending_frames = 0
        limit = 5000
        while ending_frames < limit and game.state in ("ending", "falling_text", "ending_credits"):
            if game.state == "ending_credits" and game.falling is None:
                break  # the credits are fully shown and the game waits for ENTER (not pressed: that goes to the menu)
            ending_frame()
            ending_frames += 1
            total_frames += 1
        if game.state != "ending_credits" or game.falling is not None:
            return fail(f"the ending did not reach the final credits screen (state={game.state}, "
                        f"stage={game.ending_stage}, frames={ending_frames})")
        print(f"PASS continuous run: level 1 -> {last_level}, boss defeated, final ending screen reached "
              f"(after {ending_frames} ending frames), the game was started only once (total frames={total_frames})")
        return True
    except Restarted as error:
        return fail(str(error))
    finally:
        game.new_game = real_new_game


def main():
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    last = int(sys.argv[3]) if len(sys.argv) > 3 else Config.max_levels
    failures = []
    for level_number in range(first, last + 1):
        ok, reason, frames, lives_lost = play_level(level_number)
        status = "PASS" if ok else "FAIL"
        print(f"{status} level {level_number:2d}: {reason}  (frames={frames}, lives lost={lives_lost})")
        if not ok:
            failures.append(level_number)

    print()
    print(f"levels played: {last - first + 1}, failed: {len(failures)}")
    if failures:
        print("failed levels:", failures)

    print()
    print(f"--- one continuous run: level 1 -> level {Config.max_levels} -> boss -> ending screen, the game is started only once ---")
    if (first, last) == (1, Config.max_levels):
        continuous_ok = play_continuous(Config.max_levels)
    else:
        print("skipped: it only runs when the whole range 1 to", Config.max_levels, "is tested")
        continuous_ok = True

    all_ok = not failures and continuous_ok
    print()
    print("RESULT:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
