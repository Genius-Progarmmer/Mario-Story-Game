"""The Game class: state machine, input, game logic and all screens."""

import pygame, sys, random, math, time
from debug_mode import debug_password, password_is_correct
from settings import (
    Config,
    chapters,
    chapter_for_level,
    black,
    white,
    sky,
    red,
    dark_red,
    yellow,
    green,
    dark_green,
    light_green,
    brown,
    dark_brown,
    orange,
    gray,
    light_gray,
    gold,
    cyan,
)
from utils import draw_rect
from save_system import save_game, load_game, has_save, clear_save
from sprites import draw_heart, draw_princess, draw_luigi, draw_yoshi
from effects import FallingLetters, particles, spawn_particles
from camera import Camera
from player import Mario
from companions import Companion
from level import make_bg_surface, build_level, collect_solids, enemy_body_solids, level_random

# Keys that mean the same thing (arrows and WASD).
JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)
LEFT_KEYS = (pygame.K_LEFT, pygame.K_a)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((Config.screen_width, Config.screen_height))
        pygame.display.set_caption("Super Mario Bros – Made by Mehrsam")
        self.clock = pygame.time.Clock()
        self.font_extra_large = pygame.font.Font(None, 90)
        self.font_large = pygame.font.Font(None, 64)
        self.font_medium = pygame.font.Font(None, 44)
        self.font_small = pygame.font.Font(None, 30)
        self.font_extra_small = pygame.font.Font(None, 22)
        self.font_lucky_block = pygame.font.Font(None, 28)
        self.running = True
        self.state = "menu"
        self.selected_index = 0
        self.debug_pick = 1  # the level highlighted in the debug level picker
        self.current_level = 1
        self.mario = None
        self.level = None
        self.solids = []
        self.companions = []
        self.camera = Camera()
        self.background_surface = None
        self._reset_session()
        self._build_menu()

    def _reset_session(self):
        """Forget everything that belongs to a previous run, so New Game / Continue start clean."""
        self.checkpoint_x = None
        self.flash = None
        self.falling = None
        self.fall_subtitle = ""
        self.fall_next_state = None
        self.fall_timer = 0
        self.cutscene_chapter = None
        self.cutscene_timer = 0
        self.heart_beat = 0.0
        self.heart_beat_direction = 1
        self.princess_frame = 0
        self.ending_stage = 0
        self.end_timer = 0
        self.pipe_dying = False
        self.pause_message = ""  # red text on the pause screen (e.g. the save failed)
        self.debug_active = False  # True only while playing / picking levels in debug mode (never saves)
        self.debug_input = ""  # what has been typed in the password box
        self.debug_digits = ""  # digits typed in the level picker
        self.debug_message = ""  # red / yellow line on the debug screens
        self.clock_accumulator = 0.0  # real time (ms) not yet turned into logic steps, see advance()
        particles.clear()  # in place: effects.py owns this list

    def _build_menu(self):
        options = ["New Game"]
        if has_save():
            options.append("Continue")
        if debug_password() is not None:  # the DEBUG button exists only where a .env sets a password
            options.append("Debug")
        options.append("Quit")
        self.menu_options = options
        self.selected_index = 0

    def _ground_top_at(self, x):
        """Height of the ground surface at world position x, so characters spawn standing on it."""
        ground_tops = [
            platform.top
            for platform in self.level[0]
            if platform.height >= 50 and platform.left <= x <= platform.right
        ]
        return min(ground_tops) if ground_tops else Config.ground_y

    def _load_level(self, level_number, start_x=Config.player_start_x):
        particles.clear()  # in place: effects.py owns this list
        # Seeded by the level number, so the platforms, pipes and blocks are the same every time.
        random_generator = level_random(level_number)
        self.level = build_level(level_number, random_generator, player_x=start_x)
        self.solids = collect_solids(self.level)
        ground_top = self._ground_top_at(start_x)
        self.mario = Mario(start_x, 0)
        self.mario.rect.bottom = ground_top
        chapter = chapter_for_level(level_number)
        self.companions = self._make_companions(chapter, start_x)
        for companion in self.companions:
            companion.rect.bottom = ground_top
        self.camera = Camera()
        self.camera.x = max(0, start_x - Config.screen_width // 2)
        self.pipe_dying = False
        self.background_surface = make_bg_surface(chapter)

    @staticmethod
    def _make_companions(chapter, start_x):
        """Luigi and the Princess join from chapter 2, Yoshi from chapter 3 (index = chapter - 1)."""
        luigi_offset, princess_offset, yoshi_offset = Config.companion_start_offsets
        team = []
        if chapter >= 1:
            team.append(Companion(start_x - luigi_offset, 0, "luigi", luigi_offset))
            team.append(Companion(start_x - princess_offset, 0, "princess", princess_offset))
        if chapter >= 2:
            team.append(Companion(start_x - yoshi_offset, 0, "yoshi", yoshi_offset))
        return team

    def new_game(self):
        # A brand-new run: nothing from an earlier game (state, messages, checkpoint...) may leak in.
        self._reset_session()
        self.current_level = 1
        self._load_level(1)
        self.state = "playing"
        # The old save belongs to the previous run. Replace it right now: otherwise, if the player
        # loses or quits before reaching the first checkpoint, "Continue" would silently bring
        # back the OLD game instead of the new one.
        if not self._save_progress(keep_power=False):
            removed = clear_save()  # could not overwrite it, so make sure the old one cannot be continued
            self.flash = (
                "SAVING DOES NOT WORK - progress will NOT be saved!"
                if removed
                else "WARNING: the old save could not be removed!",
                240,
            )

    def continue_game(self):
        """Load the saved level, lives, checkpoint and power, and start playing from there."""
        data = load_game()  # None unless the file is healthy: level, lives... are validated
        if data is None:
            # The file went bad after the menu was drawn: rebuild the menu so Continue disappears.
            self._build_menu()
            return
        self._reset_session()
        self.current_level = data["level"]
        self.checkpoint_x = data["checkpoint"]
        start_x = Config.player_start_x if self.checkpoint_x is None else self.checkpoint_x
        self._load_level(self.current_level, start_x)
        self.mario.lives = data["lives"]
        self.mario.power = data["power"]
        self.mario.power_timer = data["power_timer"]
        self.state = "playing"

    def _save_progress(self, keep_power=True):
        """Write level, lives, checkpoint and power to disk.

        keep_power=False is used when a new level starts: it always begins without a power.
        Returns True if the file was written.
        """
        if self.debug_active:
            return True  # debug mode must never change the real save
        mario = self.mario
        return save_game(
            self.current_level,
            mario.lives,
            self.checkpoint_x,
            mario.power if keep_power else None,
            mario.power_timer if keep_power else 0,
        )

    def _respawn(self):
        """Put Mario (and his team) back at the last checkpoint, or at the start of the level."""
        respawn_x = self.checkpoint_x if self.checkpoint_x else Config.player_start_x
        mario = self.mario
        mario.rect.x = respawn_x
        mario.rect.bottom = self._ground_top_at(respawn_x)
        mario.reset_for_respawn()
        mario.invincibility_timer = Config.invincibility_duration
        for index, companion in enumerate(self.companions):
            self._place_companion(
                companion, respawn_x - Config.companion_respawn_spacing * (index + 1)
            )
        self.camera.x = max(0, respawn_x - Config.screen_width // 2)
        self.pipe_dying = False

    @staticmethod
    def _stop_moving(character):
        character.velocity_x = 0
        character.velocity_y = 0
        character.subpixel_x = 0
        character.subpixel_y = 0

    def _place_companion(self, companion, wanted_x):
        """Stand a team member on the ground at wanted_x, but never inside a pipe or block."""
        companion.rect.x = max(0, wanted_x)
        companion.rect.bottom = self._ground_top_at(companion.rect.x)
        if companion.rect.collidelist(self.solids) != -1:
            companion.rect.x = (
                self.mario.rect.x
            )  # that spot is blocked: stand next to Mario instead
            companion.rect.bottom = self._ground_top_at(companion.rect.x)
        self._stop_moving(companion)

    def _next_level(self):
        if self.debug_active:  # in debug mode a cleared level just returns to the picker
            self._debug_return(f"LEVEL {self.current_level} CLEARED")
            return
        if self.current_level >= Config.max_levels:
            # That was the last level. There is no level 51 to move to or to save.
            self.state = "ending"
            self.ending_stage = 1
            self.end_timer = 0
            return
        self.current_level += 1
        self.checkpoint_x = None
        self._load_level(self.current_level)  # builds a new Mario first: it has the lives the new level starts with
        if not self._save_progress(keep_power=False):  # so the save matches the game; the new level has no power
            self.flash = ("SAVE FAILED - this level was NOT saved!", 240)
        # Every 10th level starts a new chapter, so show the story cutscene first.
        if self.current_level > 1 and self.current_level % 10 == 1:
            self.cutscene_chapter = chapter_for_level(self.current_level)
            self.cutscene_timer = 0
            self.state = "cutscene"
        else:
            self._trigger_fall(
                "LEVEL  " + str(self.current_level),
                yellow,
                "playing",
                subtitle=f"World {self.current_level}",
            )

    def _trigger_fall(self, text, color, next_state, subtitle=""):
        self.falling = FallingLetters(
            text,
            color,
            self.font_large,
            y_target=Config.falling_text_y,
            delay=Config.falling_text_delay,
        )
        self.fall_subtitle = subtitle
        self.fall_next_state = next_state
        self.fall_timer = 0
        self.state = "falling_text"

    # ----- Losing a life -----
    def _lose_life(self, pipe_death=False):
        """pipe_death=True starts the sinking animation; the life is taken when it has finished."""
        if pipe_death:
            self._start_pipe_death()
        else:
            self._take_life()

    def _start_pipe_death(self):
        self.pipe_dying = True
        self.mario.pipe_sink_timer = Config.pipe_sink_frames
        self.mario.pipe_sink_start_y = self.mario.rect.y
        self.mario.velocity_x = 0
        self.mario.velocity_y = 0

    def _take_life(self):
        """Remove one life, then either respawn or show GAME OVER."""
        self.mario.lives -= 1
        if self.mario.lives <= 0:
            self._game_over()
        else:
            self._respawn()
            self.flash = (f"♥ {self.mario.lives} left", Config.flash_frames_life)

    def _game_over(self):
        if self.debug_active:
            self._debug_return(f"GAME OVER ON LEVEL {self.current_level}")
            return
        self._trigger_fall("GAME  OVER", red, "menu", "Press ENTER – Made by Mehrsam")
        self._build_menu()

    # ----- Input: one handler per game state -----
    def _events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            yield event

    def handle_menu(self):
        for event in self._events():
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.selected_index = (self.selected_index - 1) % len(self.menu_options)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.selected_index = (self.selected_index + 1) % len(self.menu_options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    selected_option = self.menu_options[self.selected_index]
                    if selected_option == "New Game":
                        self.new_game()
                    elif selected_option == "Continue":
                        self.continue_game()
                    elif selected_option == "Debug":
                        self._open_debug_password()
                    elif selected_option == "Quit":
                        self.running = False

    # ----- Debug mode: password, then jump to any level (nothing is ever saved) -----
    def _open_debug_password(self):
        self.debug_input = ""
        self.debug_message = ""
        self.state = "debug_password"

    def handle_debug_password(self):
        for event in self._events():
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE:
                self.state = "menu"
                self._build_menu()
            elif event.key == pygame.K_BACKSPACE:
                self.debug_input = self.debug_input[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if password_is_correct(self.debug_input):
                    self.debug_input = ""
                    self.debug_message = ""
                    self.debug_digits = ""
                    self.state = "debug_levels"
                else:
                    self.debug_input = ""
                    self.debug_message = "WRONG PASSWORD"
            elif event.unicode and event.unicode.isprintable() and len(self.debug_input) < 40:
                self.debug_input += event.unicode

    def handle_debug_levels(self):
        for event in self._events():
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE:  # leave debug mode completely, back to the main menu
                self.debug_active = False
                self.state = "menu"
                self._build_menu()
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self.debug_pick, self.debug_digits = max(1, self.debug_pick - 1), ""
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.debug_pick, self.debug_digits = min(Config.max_levels, self.debug_pick + 1), ""
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.debug_pick, self.debug_digits = max(1, self.debug_pick - 10), ""
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.debug_pick, self.debug_digits = min(Config.max_levels, self.debug_pick + 10), ""
            elif event.unicode and event.unicode.isdigit():  # type a level number, like 27
                self.debug_digits = (self.debug_digits + event.unicode)[-2:]
                self.debug_pick = min(Config.max_levels, max(1, int(self.debug_digits)))
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.debug_start(self.debug_pick)

    def debug_start(self, level_number):
        """Play any level from its start. Lives are the normal 3. The real save is never touched."""
        level_number = min(Config.max_levels, max(1, int(level_number)))
        self._reset_session()
        self.debug_active = True
        self.debug_pick = level_number
        self.current_level = level_number
        self.checkpoint_x = None
        self._load_level(level_number)
        self.state = "playing"
        self.flash = (f"DEBUG - LEVEL {level_number}   (L = leave)", 150)

    def _debug_return(self, message=""):
        """Back to the level picker (the DEBUG 'leave'), keeping debug mode on."""
        level_number = self.current_level
        self._reset_session()
        self.debug_active = True
        self.debug_pick = level_number
        self.debug_digits = ""
        self.debug_message = message
        self.state = "debug_levels"

    def handle_play(self):
        for event in self._events():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._pause()
                    return  # everything else typed in this frame is ignored
                if event.key == pygame.K_l and self.debug_active:
                    self._debug_return("LEFT LEVEL " + str(self.current_level))
                    return
                self._handle_play_keydown(event.key)
            elif event.type == pygame.KEYUP:
                if event.key in JUMP_KEYS:
                    self.mario.release_jump()
        if not self.pipe_dying:
            self._apply_held_movement_keys()

    def _handle_play_keydown(self, key):
        mario = self.mario
        if self.pipe_dying:
            return  # Mario is sinking into a pipe: no jumping, dashing or punching
        if key in JUMP_KEYS:
            mario.press_jump()
        elif key in RIGHT_KEYS:
            mario.try_dash(1)
        elif key in LEFT_KEYS:
            mario.try_dash(-1)
        elif key == pygame.K_z:
            mario.punch()
        elif key == pygame.K_t:
            self._cycle_character()

    def _cycle_character(self):
        """T cycles through the characters Mario has unlocked (Mario + companions)."""
        unlocked = ["mario"] + [companion.kind for companion in self.companions]
        if len(unlocked) < 2:
            return
        current = self.mario.active_character
        next_index = (unlocked.index(current) + 1) % len(unlocked) if current in unlocked else 0
        wanted = unlocked[next_index]
        # The hero you stop playing takes the place (and the look) of the one you switch to,
        # so nobody is ever drawn twice.
        for companion in self.companions:
            if companion.appearance == wanted:
                companion.appearance = current
                break
        self.mario.active_character = wanted

    def _apply_held_movement_keys(self):
        """Walking follows the keys that are held down (a dash keeps its own speed)."""
        mario = self.mario
        if mario.dashing:
            return
        keys = pygame.key.get_pressed()
        if any(keys[key] for key in LEFT_KEYS):
            mario.velocity_x = -Config.player_speed
            mario.facing = -1
        elif any(keys[key] for key in RIGHT_KEYS):
            mario.velocity_x = Config.player_speed
            mario.facing = 1
        else:
            mario.velocity_x = 0

    # ----- Pause -----
    def _pause(self):
        """While paused nothing moves or attacks: update_play() is simply not called."""
        self.pause_message = ""
        self.state = "paused"

    def _resume(self):
        """Back to the game. Re-sync the input that changed while no events reached the game."""
        self.state = "playing"
        self.pause_message = ""
        keys = pygame.key.get_pressed()
        if not any(keys[key] for key in JUMP_KEYS):
            self.mario.release_jump()  # the jump key was let go during the pause
        self.mario.forget_dash_taps()

    def handle_pause(self):
        for event in self._events():
            if event.type != pygame.KEYDOWN:
                continue  # key releases, jumps, attacks... are all ignored while paused
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                self._resume()
                return
            if event.key == pygame.K_q and self.debug_active:
                self._debug_return("LEFT LEVEL " + str(self.current_level))
                return
            if event.key == pygame.K_q:
                # "SAVED!" only when the file was really written. Otherwise stay here, show the error and let the
                # player try again or keep playing: he must never think his progress is stored when it is not.
                if not self._save_progress():
                    self.pause_message = "SAVE FAILED - your progress was NOT saved!"
                    return
                self.pause_message = ""
                self._trigger_fall("SAVED!", yellow, "menu", "Made by Mehrsam")
                self._build_menu()
                return

    def handle_falling(self):
        for _ in self._events():
            pass
        self.falling.update()
        self.fall_timer += 1
        if self.falling.finished and self.fall_timer > Config.falling_text_hold_frames:
            self.state = self.fall_next_state
            self.falling = None

    def handle_cutscene(self):
        for event in self._events():
            if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_RETURN,
                pygame.K_SPACE,
                pygame.K_ESCAPE,
            ):
                self.cutscene_timer = Config.cutscene_frames + 1
        self.cutscene_timer += 1
        if self.cutscene_timer > Config.cutscene_frames:
            self.state = "falling_text"
            self._trigger_fall(
                "CHAPTER " + str(self.cutscene_chapter + 1),
                yellow,
                "playing",
                subtitle=chapters[self.cutscene_chapter][0],
            )

    def handle_ending(self):
        for event in self._events():
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.ending_stage >= 3:
                    self._build_menu()
                    self.state = "menu"

    # ----- Per-frame game logic -----
    def update_play(self):
        """One frame of gameplay.

        Every step below returns True when the frame must stop early: a life was lost or the next
        level was loaded, so the rest of the old level must not be processed any more.
        """
        if self.pipe_dying:
            self._update_pipe_death()
            return
        self._update_characters_and_effects()
        self._update_lucky_blocks()
        self._update_checkpoints()
        if (
            self._update_enemies()
            or self._update_pipes()
            or self._update_boss()
            or self._check_goal_and_pit()
        ):
            return
        self._tick_flash()

    def _update_pipe_death(self):
        """While sinking into a pipe everything else is frozen; then the life is taken."""
        self.mario.pipe_sink_timer -= 1
        if self.mario.pipe_sink_timer <= 0:
            self._take_life()

    def _update_characters_and_effects(self):
        self.mario.update(self.solids)
        for companion in self.companions:
            companion.update(self.mario, self.solids)
        self.camera.update(self.mario.rect.x)
        self._beat_heart()
        for particle in particles[:]:
            particle.update()
        particles[:] = [particle for particle in particles if particle.alive]

    def _beat_heart(self):
        self.heart_beat += Config.heart_beat_speed * self.heart_beat_direction
        if self.heart_beat >= 1:
            self.heart_beat_direction = -1
        elif self.heart_beat <= 0:
            self.heart_beat_direction = 1

    # ----- Lucky blocks and checkpoints -----
    def _update_lucky_blocks(self):
        """First touch of a block gives a timed power-up (3 seconds).

        Blocks are solid, so Mario's rectangle only ever *touches* them and never overlaps; that is
        why the touch test looks a pixel around him.
        """
        touch_area = self.mario.rect.inflate(
            2 * Config.block_touch_margin, 2 * Config.block_touch_margin
        )
        for lucky_block in self.level[4]:
            lucky_block.update()
            if lucky_block.used or not touch_area.colliderect(lucky_block.rect):
                continue
            if lucky_block.try_hit():
                self._give_power(lucky_block)

    def _give_power(self, lucky_block):
        mario = self.mario
        if mario.velocity_y < 0:
            mario.velocity_y = Config.block_bump_speed  # bumped the head: bounce back down
        mario.power = lucky_block.reward
        mario.power_timer = Config.power_duration_frames
        spawn_particles(lucky_block.rect.centerx, lucky_block.rect.top, gold, count=8, spread=4)
        self.camera.shake(Config.shake_block)
        self.flash = (f"★ {lucky_block.reward.upper()} POWER!", Config.flash_frames_power)

    def _update_checkpoints(self):
        """Touching a checkpoint remembers the position and auto-saves."""
        for checkpoint in self.level[3]:
            checkpoint.update()
            if not checkpoint.activated and self.mario.rect.colliderect(checkpoint.rect):
                checkpoint.activated = True
                self.checkpoint_x = checkpoint.world_x
                if self._save_progress():
                    self.flash = ("✔ CHECKPOINT!", Config.flash_frames_checkpoint)
                else:
                    self.flash = ("CHECKPOINT - but SAVE FAILED!", 220)

    # ----- Enemies -----
    def _update_enemies(self):
        """Crush power or a punch kills instantly; stomping from above kills; side contact costs a life."""
        enemies = self.level[1]
        live_enemies = [enemy for enemy in enemies if enemy.alive and enemy.squish == 0]
        for enemy in enemies[:]:
            if not enemy.alive:
                # A defeated enemy stays on screen as a squashed sprite until its squish timer runs out
                # (the draw code stops drawing it at 0). Only the timer ticks: the enemy is not updated, so it never moves.
                if enemy.squish > 0:
                    enemy.squish -= 1
                continue
            enemy_solids = self.solids + enemy_body_solids(live_enemies, enemy)
            enemy.update(enemy_solids, self.solids)
            if not enemy.alive:
                continue
            if self._enemy_hit_by_power_or_punch(enemy):
                continue
            if self._mario_touches_enemy(enemy):
                return True
        return False

    def _kill_enemy(self, enemy, particle_color, shake=0):
        enemy.squish = Config.enemy_squish_frames
        enemy.alive = False
        spawn_particles(enemy.rect.centerx, enemy.rect.top, particle_color, count=8, spread=5)
        if shake:
            self.camera.shake(shake)

    def _punch_area(self, size):
        """The rectangle in front of Mario that a punch hits."""
        width, height = size
        left = self.mario.rect.centerx + (0 if self.mario.facing > 0 else -width)
        return pygame.Rect(left, self.mario.rect.y + Config.punch_y_offset, width, height)

    def _crush_reaches(self, enemy):
        """CRUSH hits only enemies that are really NEAR Mario: close horizontally AND close vertically
        (centre to centre). The same test is used when the power starts and for as long as it lasts."""
        mario_rect, enemy_rect = self.mario.rect, enemy.rect
        return (abs(enemy_rect.centerx - mario_rect.centerx) < Config.crush_power_range
                and abs(enemy_rect.centery - mario_rect.centery) < Config.crush_power_range_y)

    def _enemy_hit_by_power_or_punch(self, enemy):
        mario = self.mario
        if mario.power == "crush" and self._crush_reaches(enemy):
            self._kill_enemy(enemy, orange)
            return True
        if mario.punch_timer > 0 and self._punch_area(Config.punch_enemy_size).colliderect(
            enemy.rect
        ):
            self._kill_enemy(enemy, yellow, Config.shake_punch)
            return True
        return False

    def _is_stomp(self, target_rect, tolerance):
        """True when Mario is falling and was above the target's top edge on the previous frame."""
        mario = self.mario
        came_from_above = mario.rect.bottom - mario.velocity_y <= target_rect.top + tolerance
        return mario.velocity_y > 0 and came_from_above

    def _mario_touches_enemy(self, enemy):
        """Returns True if Mario lost a life."""
        mario = self.mario
        if not mario.rect.colliderect(enemy.rect):
            return False
        if self._is_stomp(enemy.rect, Config.stomp_tolerance_enemy):
            self._kill_enemy(enemy, red, Config.shake_stomp)
            mario.velocity_y = Config.stomp_bounce_enemy
            mario.jump_held = False
            return False
        if mario.invincibility_timer == 0:
            self._lose_life()
            return True
        return False

    # ----- Pipes -----
    def _update_pipes(self):
        """Pipes are solid. With Config.pipe_top_kills on, standing on the middle of the top kills
        Mario; the overhanging edge of the lip is not solid, so touching it does nothing."""
        mario = self.mario
        for pipe in self.level[2]:
            self._push_out_of_pipe(pipe)
            if (
                Config.pipe_top_kills
                and self._standing_on_pipe_top(pipe)
                and mario.invincibility_timer == 0
            ):
                self._lose_life(pipe_death=True)
                return True
        return False

    def _push_out_of_pipe(self, pipe):
        """Safety net: normal movement already stops Mario at the pipe wall, but if he ever ends
        up overlapping the pipe body, move him out on the nearer side."""
        mario = self.mario
        if not mario.rect.colliderect(pipe.shaft):
            return
        overlap_left = mario.rect.right - pipe.shaft.left
        overlap_right = pipe.shaft.right - mario.rect.left
        if overlap_left < overlap_right:
            mario.rect.right = pipe.shaft.left
        else:
            mario.rect.left = pipe.shaft.right
        mario.velocity_x = 0
        mario.subpixel_x = 0
        mario.dashing = False

    def _standing_on_pipe_top(self, pipe):
        mario = self.mario
        return (
            mario.on_ground
            and mario.rect.bottom == pipe.lip_center.top
            and mario.rect.right > pipe.lip_center.left
            and mario.rect.left < pipe.lip_center.right
        )

    # ----- Boss -----
    def _update_boss(self):
        """Dodge its shells, punch or stomp it. The goal stays locked until it is dead."""
        boss = self.level[5]
        if not (boss and boss.alive):
            return False
        boss.update(self.mario.rect.x, self.solids)
        if self._boss_shell_hits_mario(boss):
            return True
        self._punch_boss(boss)
        if not boss.alive:  # that punch was the last hit: a dead boss can no longer hurt Mario
            return False
        return self._mario_touches_boss(boss)

    def _boss_shell_hits_mario(self, boss):
        mario = self.mario
        half = Config.boss_shell_size // 2
        for shell in boss.projectiles[:]:
            shell_rect = pygame.Rect(
                int(shell["x"] - half),
                int(shell["y"] - half),
                Config.boss_shell_size,
                Config.boss_shell_size,
            )
            if mario.rect.colliderect(shell_rect) and mario.invincibility_timer == 0:
                boss.projectiles.remove(shell)
                self._lose_life()
                return True
        return False

    def _damage_boss(self, boss):
        """One hit of damage; returns True when that was the last hit."""
        if boss.take_damage():
            boss.alive = False
            spawn_particles(boss.rect.centerx, boss.rect.top, orange, count=20, spread=8)
            self.camera.shake(Config.shake_boss_defeated)
            return True
        return False

    def _punch_boss(self, boss):
        mario = self.mario
        if mario.punch_timer <= 0 or boss.hurt != 0:
            return
        if not self._punch_area(Config.punch_boss_size).colliderect(boss.rect):
            return
        mario.punch_timer = 0  # one punch = one hit
        if not self._damage_boss(boss):
            self.flash = ("BOSS HIT!", Config.flash_frames_boss_hit)
            self.camera.shake(Config.shake_boss_hit)

    def _mario_touches_boss(self, boss):
        """Returns True if Mario lost a life. A defeated boss never costs one."""
        mario = self.mario
        if not boss.alive or not mario.rect.colliderect(boss.rect):
            return False
        if self._is_stomp(boss.rect, Config.stomp_tolerance_boss):
            # A fast fall sinks Mario up to 18px into the boss, and the bounce (which fades quickly) may not lift him
            # out in one frame: the NEXT frame he would still overlap the boss while rising, count as a side touch and
            # lose a life for a successful stomp. So he is put on top of the boss first.
            mario.rect.bottom = boss.rect.top
            mario.subpixel_y = 0
            mario.velocity_y = Config.stomp_bounce_boss
            mario.jump_held = False
            self._damage_boss(boss)
            return False
        if mario.invincibility_timer == 0:
            self._lose_life()
            return True
        return False

    # ----- Goal, pits and messages -----
    def _check_goal_and_pit(self):
        platforms, enemies, pipes, checkpoints, lucky_blocks, boss, goal = self.level
        if self.mario.rect.colliderect(goal) and not (boss and boss.alive):
            self._next_level()
            return True
        if self.mario.rect.y > Config.screen_height + Config.fall_death_margin:
            self._lose_life()
            return True
        return False

    def _tick_flash(self):
        if self.flash:
            flash_text, flash_time = self.flash
            self.flash = (flash_text, flash_time - 1) if flash_time > 1 else None

    def update_ending(self):
        self.end_timer += 1
        self.princess_frame += 1
        timer = self.end_timer
        if self.ending_stage == 1 and timer > Config.ending_walk_frames:
            self.ending_stage = 2
            self.end_timer = 0
        elif self.ending_stage == 2 and timer > Config.ending_hearts_frames:
            self.ending_stage = 3
            self.end_timer = 0
            self._trigger_fall(
                "MADE  BY  MEHRSAM", gold, "ending_credits", "Thank you for playing!"
            )

    # ----- Drawing -----
    def _draw_sky(self, camera_x):
        if self.background_surface:
            background_x = max(0, min(Config.level_width - Config.screen_width, int(camera_x)))
            self.screen.blit(
                self.background_surface,
                (0, 0),
                (background_x, 0, Config.screen_width, Config.screen_height),
            )
        else:
            self.screen.fill(sky)

    def _draw_level(self, camera_x):
        platforms, enemies, pipes, checkpoints, lucky_blocks, boss, goal = self.level
        for platform in platforms:
            screen_x = platform.x - camera_x
            if screen_x + platform.w < 0 or screen_x > Config.screen_width:
                continue
            if platform.h >= 50:
                draw_rect(self.screen, dark_brown, screen_x, platform.y, platform.w, platform.h)
                draw_rect(self.screen, green, screen_x, platform.y, platform.w, 10)
                pygame.draw.rect(self.screen, dark_green, (screen_x, platform.y, platform.w, 10), 1)
                for column_x in range(0, platform.w, 32):
                    pygame.draw.line(
                        self.screen,
                        brown,
                        (screen_x + column_x, platform.y + 10),
                        (screen_x + column_x, platform.y + platform.h),
                        1,
                    )
                for row_y in range(platform.y + 22, platform.y + platform.h, 16):
                    pygame.draw.line(
                        self.screen, brown, (screen_x, row_y), (screen_x + platform.w, row_y), 1
                    )
            else:
                draw_rect(self.screen, green, screen_x, platform.y, platform.w, platform.h)
                draw_rect(
                    self.screen, dark_green, screen_x, platform.y + 4, platform.w, platform.h - 4
                )
                draw_rect(self.screen, light_green, screen_x, platform.y, platform.w, 4)
                pygame.draw.rect(
                    self.screen, dark_green, (screen_x, platform.y, platform.w, platform.h), 2
                )
        for pipe in pipes:
            pipe.draw(self.screen, camera_x)
        for lucky_block in lucky_blocks:
            lucky_block.draw(self.screen, camera_x, self.font_lucky_block)
        for checkpoint in checkpoints:
            checkpoint.draw(self.screen, camera_x)
        for enemy in enemies:
            if enemy.alive or enemy.squish > 0:
                if -40 < enemy.rect.x - camera_x < Config.screen_width + 40:
                    enemy.draw(self.screen, camera_x)
        if boss and boss.alive:
            if -100 < boss.rect.x - camera_x < Config.screen_width + 100:
                boss.draw(self.screen, camera_x)
                boss.draw_projectiles(self.screen, camera_x)
        for companion in self.companions:
            if -60 < companion.rect.x - camera_x < Config.screen_width + 60:
                companion.draw(self.screen, camera_x)
        goal_screen_x = goal.x - camera_x
        if -60 < goal_screen_x < Config.screen_width + 60:
            draw_rect(self.screen, (200, 200, 0), goal_screen_x, goal.y, goal.w, goal.h)
            draw_rect(self.screen, yellow, goal_screen_x + 2, goal.y + 2, goal.w - 4, goal.h - 4)
            draw_rect(self.screen, black, goal_screen_x + 15, goal.y, 5, goal.h + 20)
            pygame.draw.polygon(
                self.screen,
                red,
                [
                    (goal_screen_x + 20, goal.y),
                    (goal_screen_x + 44, goal.y + 12),
                    (goal_screen_x + 20, goal.y + 24),
                ],
            )

    def _draw_hud(self):
        for index in range(self.mario.lives):
            beat = self.heart_beat if index == 0 else self.heart_beat * 0.7
            draw_heart(self.screen, 18 + index * 30, 22, 10, dark_red, beat)
            draw_heart(self.screen, 18 + index * 30, 22, 9, red, beat)
        level_label = self.font_small.render(
            f"LV{self.current_level}/{Config.max_levels}", True, white
        )
        self.screen.blit(level_label, (Config.screen_width - level_label.get_width() - 8, 8))
        if self.mario.power and self.mario.power_timer > 0:
            colors = {"fly": cyan, "crush": orange, "jump": light_green}
            label = self.font_extra_small.render(
                f"{self.mario.power.upper()} {self.mario.power_timer//Config.frames_per_second+1}s",
                True,
                colors.get(self.mario.power, white),
            )
            self.screen.blit(label, (8, 54))
            pygame.draw.rect(self.screen, black, (8, 78, 150, 10))
            pygame.draw.rect(
                self.screen,
                colors.get(self.mario.power, white),
                (9, 79, int(148 * self.mario.power_timer / Config.power_duration_frames), 8),
            )
        if self.companions:
            team = self.font_extra_small.render(
                "TEAM: " + ", ".join(companion.appearance.title() for companion in self.companions),
                True,
                light_green,
            )
            self.screen.blit(team, (8, 92))
        if self.mario.dashing:
            dash_text = self.font_small.render("DASH!", True, cyan)
            self.screen.blit(dash_text, (Config.screen_width // 2 - dash_text.get_width() // 2, 50))
        platforms, enemies, pipes, checkpoints, lucky_blocks, boss, goal = self.level
        if boss and boss.alive:
            boss_text = self.font_medium.render("BOSS! JUMP ON HEAD!", True, red)
            self.screen.blit(boss_text, boss_text.get_rect(center=(Config.screen_width // 2, 28)))
        if self.flash:
            flash_surface = self.font_small.render(self.flash[0], True, yellow)
            flash_surface.set_alpha(min(255, self.flash[1] * 4))
            self.screen.blit(
                flash_surface,
                flash_surface.get_rect(
                    center=(Config.screen_width // 2, Config.screen_height - 44)
                ),
            )
        controls_hint = self.font_extra_small.render(
            "TAP >> TWICE = DASH BOOST", True, (100, 200, 255)
        )
        self.screen.blit(
            controls_hint,
            (Config.screen_width // 2 - controls_hint.get_width() // 2, Config.screen_height - 20),
        )

    def draw_play(self):
        camera_x = int(self.camera.x) + self.camera.shake_offset_x
        self._draw_sky(camera_x)
        self._draw_level(camera_x)
        for particle in particles:
            particle.draw(self.screen, camera_x)
        self.mario.draw(self.screen, camera_x)
        self._draw_hud()
        if self.debug_active:  # always visible, so a debug run is never mistaken for a real one
            tag = self.font_extra_small.render(f"DEBUG  level {self.current_level}  -  L = leave", True, yellow)
            box = tag.get_rect(bottomleft=(8, Config.screen_height - 8)).inflate(12, 8)
            pygame.draw.rect(self.screen, (120, 0, 0), box)
            self.screen.blit(tag, tag.get_rect(center=box.center))

    def draw_pause(self):
        self.draw_play()
        overlay = pygame.Surface((Config.screen_width, Config.screen_height))
        overlay.set_alpha(145)
        overlay.fill(black)
        self.screen.blit(overlay, (0, 0))
        title_text = self.font_large.render("PAUSED", True, white)
        self.screen.blit(title_text, title_text.get_rect(center=(Config.screen_width // 2, 190)))
        pause_lines = ["ESC/ENTER – Resume", "Q – Leave debug level" if self.debug_active else "Q – Save & quit"]
        for index, line in enumerate(pause_lines):
            line_text = self.font_small.render(line, True, light_gray)
            self.screen.blit(
                line_text, line_text.get_rect(center=(Config.screen_width // 2, 300 + index * 46))
            )
        if self.pause_message:
            box = pygame.Rect(0, 0, 680, 70)
            box.center = (Config.screen_width // 2, 430)
            pygame.draw.rect(self.screen, dark_red, box)
            pygame.draw.rect(self.screen, white, box, 2)
            message = self.font_small.render(self.pause_message, True, white)
            self.screen.blit(message, message.get_rect(center=(box.centerx, box.y + 22)))
            hint = self.font_extra_small.render(
                "Press Q to try again, or ESC to keep playing", True, light_gray
            )
            self.screen.blit(hint, hint.get_rect(center=(box.centerx, box.y + 50)))

    def draw_debug_password(self):
        self.screen.fill((20, 20, 40))
        centre = Config.screen_width // 2
        title = self.font_large.render("DEBUG MODE", True, yellow)
        self.screen.blit(title, title.get_rect(center=(centre, 150)))
        prompt = self.font_small.render("Enter the password and press ENTER", True, white)
        self.screen.blit(prompt, prompt.get_rect(center=(centre, 240)))
        box = pygame.Rect(0, 0, 360, 56)
        box.center = (centre, 320)
        pygame.draw.rect(self.screen, black, box)
        pygame.draw.rect(self.screen, white, box, 2)
        stars = self.font_medium.render("*" * len(self.debug_input), True, white)  # never show what was typed
        self.screen.blit(stars, stars.get_rect(center=box.center))
        if self.debug_message:
            message = self.font_small.render(self.debug_message, True, red)
            self.screen.blit(message, message.get_rect(center=(centre, 390)))
        hint = self.font_extra_small.render("ESC – back to the menu", True, light_gray)
        self.screen.blit(hint, hint.get_rect(center=(centre, 520)))

    def draw_debug_levels(self):
        self.screen.fill((20, 20, 40))
        centre = Config.screen_width // 2
        title = self.font_large.render("DEBUG - PICK A LEVEL", True, yellow)
        self.screen.blit(title, title.get_rect(center=(centre, 60)))
        cell_w, cell_h, columns = 66, 46, 10
        left = (Config.screen_width - columns * cell_w) // 2
        for number in range(1, Config.max_levels + 1):
            row, column = divmod(number - 1, columns)
            cell = pygame.Rect(left + column * cell_w + 3, 120 + row * (cell_h + 6), cell_w - 6, cell_h)
            chosen = number == self.debug_pick
            boss = number % 10 == 0
            fill = (150, 0, 0) if boss else (0, 0, 90)
            pygame.draw.rect(self.screen, (200, 160, 0) if chosen else fill, cell)
            pygame.draw.rect(self.screen, white if chosen else light_gray, cell, 3 if chosen else 1)
            label = self.font_small.render(str(number), True, black if chosen else white)
            self.screen.blit(label, label.get_rect(center=cell.center))
        chapter = chapter_for_level(self.debug_pick) + 1
        info = f"Level {self.debug_pick}   -   Chapter {chapter}" + ("   -   BOSS" if self.debug_pick % 10 == 0 else "")
        line = self.font_medium.render(info, True, white)
        self.screen.blit(line, line.get_rect(center=(centre, 440)))
        if self.debug_message:
            message = self.font_small.render(self.debug_message, True, yellow)
            self.screen.blit(message, message.get_rect(center=(centre, 490)))
        hint = self.font_extra_small.render(
            "Arrows move (up / down = 10)  -  type a number  -  ENTER start  -  ESC leave debug", True, light_gray
        )
        self.screen.blit(hint, hint.get_rect(center=(centre, 550)))

    def draw_menu(self):
        if self.background_surface:
            self.screen.blit(
                self.background_surface, (0, 0), (0, 0, Config.screen_width, Config.screen_height)
            )
        else:
            self.screen.fill(sky)
        draw_rect(self.screen, dark_brown, 0, 548, Config.screen_width, 52)
        draw_rect(self.screen, green, 0, 548, Config.screen_width, 10)
        title_shadow = self.font_extra_large.render("SUPER MARIO BROS", True, dark_red)
        title_text = self.font_extra_large.render("SUPER MARIO BROS", True, red)
        self.screen.blit(
            title_shadow, title_shadow.get_rect(center=(Config.screen_width // 2 + 3, 143))
        )
        self.screen.blit(title_text, title_text.get_rect(center=(Config.screen_width // 2, 140)))
        subtitle_text = self.font_small.render("Made by  M e h r s a m", True, yellow)
        self.screen.blit(
            subtitle_text, subtitle_text.get_rect(center=(Config.screen_width // 2, 196))
        )
        for index, option in enumerate(self.menu_options):
            text_color = yellow if index == self.selected_index else white
            box_color = (120, 0, 0) if index == self.selected_index else (0, 0, 80)
            option_text = self.font_medium.render(option, True, text_color)
            option_rect = option_text.get_rect(center=(Config.screen_width // 2, 296 + index * 58))
            pygame.draw.rect(self.screen, box_color, option_rect.inflate(24, 10), border_radius=5)
            self.screen.blit(option_text, option_rect)
        hint = self.font_extra_small.render(
            "Arrows/WASD: move  SPACE: jump*2  TAP>> DASH  ESC: pause", True, light_gray
        )
        self.screen.blit(hint, hint.get_rect(center=(Config.screen_width // 2, 515)))

    def draw_falling(self):
        self.screen.fill((10, 5, 20))
        star_random_generator = random.Random(42)
        for _ in range(80):
            self.screen.set_at(
                (
                    star_random_generator.randint(0, Config.screen_width),
                    star_random_generator.randint(0, Config.screen_height),
                ),
                white,
            )
        if self.falling:
            self.falling.draw(self.screen)
        if self.fall_subtitle:
            subtitle_text = self.font_small.render(self.fall_subtitle, True, light_gray)
            self.screen.blit(
                subtitle_text, subtitle_text.get_rect(center=(Config.screen_width // 2, 340))
            )
        hint = self.font_extra_small.render("(continuing...)", True, gray)
        self.screen.blit(
            hint, hint.get_rect(center=(Config.screen_width // 2, Config.screen_height - 30))
        )

    def draw_cutscene(self):
        chapter = self.cutscene_chapter or 0
        self.screen.fill((8, 4, 20))
        colors = [(40, 120, 210), (100, 35, 150), (12, 25, 100), (180, 45, 10), (45, 15, 90)]
        pygame.draw.rect(self.screen, colors[chapter], (0, 300, Config.screen_width, 250))
        pygame.draw.circle(self.screen, (255, 220, 120), (650, 110), 45)
        for index in range(8):
            pygame.draw.polygon(
                self.screen,
                (10, 8, 25),
                [(index * 120 - 30, 500), (index * 120 + 45, 330), (index * 120 + 120, 500)],
            )
        title = self.font_large.render("CHAPTER %d" % (chapter + 1), True, yellow)
        self.screen.blit(title, title.get_rect(center=(Config.screen_width // 2, 105)))
        name, story = chapters[chapter]
        name_text = self.font_medium.render(name, True, white)
        self.screen.blit(name_text, name_text.get_rect(center=(Config.screen_width // 2, 180)))
        # Word-wrap the story text to fit the screen.
        words, line = story.split(), ""
        lines = []
        for word in words:
            if self.font_extra_small.size(line + " " + word)[0] > 680:
                lines.append(line)
                line = word
            else:
                line = (line + " " + word).strip()
        if line:
            lines.append(line)
        for index, text in enumerate(lines):
            story_text = self.font_extra_small.render(text, True, light_gray)
            self.screen.blit(
                story_text, story_text.get_rect(center=(Config.screen_width // 2, 240 + index * 28))
            )
        if chapter >= 1:
            draw_luigi(self.screen, 300, 430, 1, self.cutscene_timer // 8 % 2)
        draw_princess(self.screen, 465, 425, self.cutscene_timer // 8 % 2)
        draw_yoshi(self.screen, 540, 440, 1, self.cutscene_timer // 8 % 2)
        hint = self.font_extra_small.render("ENTER / SPACE to skip", True, gray)
        self.screen.blit(hint, hint.get_rect(center=(Config.screen_width // 2, 570)))

    def draw_ending(self):
        if self.background_surface:
            self.screen.blit(
                self.background_surface, (0, 0), (0, 0, Config.screen_width, Config.screen_height)
            )
        else:
            self.screen.fill(sky)
        draw_rect(self.screen, dark_brown, 0, 548, Config.screen_width, 52)
        draw_rect(self.screen, green, 0, 548, Config.screen_width, 10)
        timer = self.end_timer
        if self.ending_stage == 1:
            mario_x = min(Config.screen_width // 2 - 40, 60 + timer * 3)
            ending_mario = Mario(int(mario_x), 490)
            ending_mario.facing = 1
            ending_mario.invincibility_timer = 0
            ending_mario.walk_frame = timer // 7 % 2
            ending_mario.on_ground = True
            ending_mario.velocity_x = 1
            ending_mario.squash = 0
            ending_mario.draw(self.screen, 0)
            message = self.font_medium.render("The princess is rescued!", True, white)
            self.screen.blit(message, message.get_rect(center=(Config.screen_width // 2, 160)))
        elif self.ending_stage == 2:
            draw_princess(self.screen, Config.screen_width // 2 + 30, 456, self.princess_frame)
            ending_mario = Mario(Config.screen_width // 2 - 60, 490)
            ending_mario.facing = 1
            ending_mario.invincibility_timer = 0
            ending_mario.walk_frame = 0
            ending_mario.on_ground = True
            ending_mario.velocity_x = 0
            ending_mario.squash = 0
            ending_mario.draw(self.screen, 0)
            for index in range(min(14, timer // 18 + 1)):
                heart_x = (
                    Config.screen_width // 2 - 10 + int(55 * math.cos(index * 0.45 + timer * 0.025))
                )
                heart_y = 370 + int(40 * math.sin(index * 0.45 + timer * 0.03))
                draw_heart(
                    self.screen,
                    heart_x,
                    heart_y,
                    10,
                    red,
                    abs(math.sin(timer * 0.06 + index * 0.5)),
                )
            title_text = self.font_large.render("Happily ever after!", True, gold)
            subtitle_text = self.font_small.render("Mario married the princess!", True, white)
            self.screen.blit(
                title_text, title_text.get_rect(center=(Config.screen_width // 2, 160))
            )
            self.screen.blit(
                subtitle_text, subtitle_text.get_rect(center=(Config.screen_width // 2, 215))
            )
        elif self.ending_stage == 3:
            if self.falling:
                self.falling.draw(self.screen)

    def draw_ending_credits(self):
        self.screen.fill((5, 0, 15))
        star_random_generator = random.Random(99)
        for _ in range(100):
            self.screen.set_at(
                (
                    star_random_generator.randint(0, Config.screen_width),
                    star_random_generator.randint(0, Config.screen_height),
                ),
                white,
            )
        if self.falling:
            self.falling.draw(self.screen)
        if self.fall_subtitle:
            subtitle_text = self.font_medium.render(self.fall_subtitle, True, light_gray)
            self.screen.blit(
                subtitle_text, subtitle_text.get_rect(center=(Config.screen_width // 2, 340))
            )
        made_by_text = self.font_small.render(
            "Super Mario Bros – Made by Mehrsam – 50 levels!", True, gold
        )
        self.screen.blit(
            made_by_text, made_by_text.get_rect(center=(Config.screen_width // 2, 400))
        )
        hint = self.font_extra_small.render("Press ENTER for menu", True, gray)
        self.screen.blit(
            hint, hint.get_rect(center=(Config.screen_width // 2, Config.screen_height - 28))
        )

    def _play_step(self):
        """Input, then update. If ESC paused the game, this step does no updating. (No drawing.)"""
        self.handle_play()
        if self.state == "playing":
            self.update_play()

    def _play_frame(self):
        """One step plus drawing (the tests drive the game with this)."""
        self._play_step()
        self.draw_play()

    def _update_ending_credits(self):
        self.handle_ending()
        if self.falling:
            self.falling.update()
            self.fall_timer += 1
            if self.falling.finished and self.fall_timer > Config.credits_hold_frames:
                self.falling = None

    def _logic_step(self):
        """ONE step of game logic (input + update) for the current state. Nothing is drawn here."""
        if self.state == "menu":
            self.handle_menu()
        elif self.state == "playing":
            self._play_step()
        elif self.state == "paused":
            self.handle_pause()
        elif self.state == "falling_text":
            self.handle_falling()
        elif self.state == "cutscene":
            self.handle_cutscene()
        elif self.state == "ending":
            self.handle_ending()
            self.update_ending()
        elif self.state == "ending_credits":
            self._update_ending_credits()
        elif self.state == "debug_password":
            self.handle_debug_password()
        elif self.state == "debug_levels":
            self.handle_debug_levels()

    def _draw_state(self):
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "playing":
            self.draw_play()
        elif self.state == "paused":
            self.draw_pause()
        elif self.state == "falling_text":
            if self.falling:
                self.draw_falling()
        elif self.state == "cutscene":
            self.draw_cutscene()
        elif self.state == "ending":
            self.draw_ending()
        elif self.state == "ending_credits":
            self.draw_ending_credits()
        elif self.state == "debug_password":
            self.draw_debug_password()
        elif self.state == "debug_levels":
            self.draw_debug_levels()

    def steps_for(self, elapsed_ms):
        """Turn REAL elapsed time into a number of logic steps (the game logic always runs at
        Config.frames_per_second steps per real second, whatever the speed of the computer).

        Everything that is counted in frames (powers, invincibility, cutscenes...) used to take longer in real time
        whenever the screen could not keep up with 60 fps. If far more steps are owed than
        Config.max_catch_up_steps (a frozen window, a very slow computer) the backlog is dropped and the game
        slows down instead of trying to catch up for ever.
        """
        step_ms = 1000.0 / Config.frames_per_second
        self.clock_accumulator += max(0.0, elapsed_ms)
        steps = int(self.clock_accumulator / step_ms + 1e-9)
        if steps > Config.max_catch_up_steps:
            steps = Config.max_catch_up_steps
            self.clock_accumulator = 0.0
        else:
            self.clock_accumulator = max(0.0, self.clock_accumulator - steps * step_ms)
        return steps

    def advance(self, elapsed_ms):
        """One drawn frame: run the logic steps that the elapsed real time owes, then draw once."""
        steps = self.steps_for(elapsed_ms)
        if steps == 0:
            pygame.event.pump()  # keep the window alive even when no step is due
        for _ in range(steps):
            self._logic_step()
        self._draw_state()

    def run(self):
        # Main loop: a simple state machine. Each state has an input handler plus update/draw.
        last_time = time.perf_counter()
        while self.running:
            now = time.perf_counter()
            self.advance((now - last_time) * 1000.0)
            last_time = now
            pygame.display.flip()
            self.clock.tick(Config.frames_per_second)
        pygame.quit()
        sys.exit()
