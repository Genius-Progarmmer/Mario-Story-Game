"""The player character (Mario): movement, jumping, dashing, punching and drawing."""

import pygame
from settings import (
    Config,
    black,
    white,
    red,
    yellow,
    skin,
    cyan,
)
from utils import draw_rect, draw_circle, move_with_collision
from effects import spawn_particles, spawn_dash_trail
from sprites import draw_luigi, draw_princess, draw_yoshi, PRINCESS_SINK

normal_palette = {
    "hat": (200, 20, 20),
    "skin": (255, 210, 155),
    "overalls": (50, 80, 210),
    "shirt": (220, 40, 40),
    "boot": (80, 45, 10),
    "mustache": (90, 50, 15),
    "hair": (100, 55, 15),
    "button": (255, 215, 0),
    "shadow": (180, 135, 95),
}
dash_palette = {
    "hat": (0, 200, 220),
    "skin": (200, 245, 255),
    "overalls": (0, 140, 220),
    "shirt": (0, 220, 255),
    "boot": (0, 90, 120),
    "mustache": (0, 120, 150),
    "hair": (0, 150, 180),
    "button": (255, 255, 0),
    "shadow": (140, 210, 230),
}


class Mario:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, Config.player_width, Config.player_height)
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.subpixel_x = 0.0  # leftover fractions of a pixel (see utils.move_with_collision)
        self.subpixel_y = 0.0
        self.on_ground = False
        self.was_on_ground = False
        self.jumps_left = 2
        self.lives = Config.starting_lives
        self.facing = 1
        self.invincibility_timer = 0
        self.walk_timer = 0
        self.walk_frame = 0
        self.idle_timer = 0
        self.jump_held = False
        self.jump_frames = 0
        self.squash = 0.0
        self.pipe_sink_timer = 0
        self.pipe_sink_start_y = 0
        self.dashing = False
        self.dash_timer = 0
        self.dash_cooldown = 0
        self.last_right_tap_frame = -99
        self.last_left_tap_frame = -99
        self.frame_count = 0
        self.power = None
        self.power_timer = 0
        self.fly_input = 0               # -1 = rise (UP / SPACE / W held), +1 = sink (DOWN / S held), 0 = hover
        self.boss_hits = 0               # hits taken in the current boss fight (reset on every life, like the HTML game)
        self.punch_timer = 0
        self.active_character = "mario"

    # ----- Actions triggered by input -----
    def punch(self):
        """Short-range attack (Z key). Ignored while a punch is already in progress."""
        if self.punch_timer == 0:
            self.punch_timer = Config.punch_duration
            spawn_particles(
                self.rect.centerx + self.facing * 24, self.rect.centery, yellow, count=4, spread=2
            )

    def press_jump(self):
        """Start a jump. Mario has two jumps; landing gives both back (see update)."""
        if self.jumps_left <= 0:
            return
        first_jump = self.jumps_left == 2
        if self.power == "jump":
            self.velocity_y = (
                Config.power_jump_speed if first_jump else Config.power_double_jump_speed
            )
        else:
            self.velocity_y = (
                Config.player_jump_speed if first_jump else Config.player_double_jump_speed
            )
        self.jumps_left -= 1
        self.on_ground = False
        self.jump_held = True
        self.jump_frames = 0
        self.squash = Config.squash_on_jump

    def release_jump(self):
        self.jump_held = False

    def reset_for_respawn(self):
        """Forget everything that belongs to the previous life (the caller has already placed
        Mario standing on the ground at the respawn point).

        Without this, a death in mid-air could leave jumps_left at 0 or jump_held at True, and
        the first jump key press after the respawn would be ignored.
        """
        self.velocity_x = self.velocity_y = 0.0
        self.subpixel_x = self.subpixel_y = 0.0
        self.boss_hits = 0               # a new life starts the boss fight with all hearts again
        self.fly_input = 0
        self.on_ground = True            # he is standing on the ground right now
        self.was_on_ground = True        # ...so no "landing" squash or dust puff on the first frame
        self.jumps_left = 2              # both jumps are available immediately
        self.jump_held = False
        self.jump_frames = 0
        self.squash = 0.0
        self.dashing = False
        self.dash_timer = 0
        self.punch_timer = 0
        self.pipe_sink_timer = 0
        self.forget_dash_taps()

    def forget_dash_taps(self):
        """Forget earlier arrow-key taps, so a tap before a pause and a tap after it are not a double-tap."""
        self.last_right_tap_frame = -99
        self.last_left_tap_frame = -99

    def try_dash(self, direction):
        """Two quick taps in the same direction start a dash (unless the dash is cooling down)."""
        current_frame = self.frame_count
        if direction == 1:
            last_tap = self.last_right_tap_frame
            self.last_right_tap_frame = current_frame
        else:
            last_tap = self.last_left_tap_frame
            self.last_left_tap_frame = current_frame
        is_double_tap = current_frame - last_tap < Config.double_tap_window
        if is_double_tap and self.dash_cooldown == 0:
            self._start_dash(direction)

    def _start_dash(self, direction):
        self.dashing = True
        self.dash_timer = Config.dash_duration
        self.dash_cooldown = Config.dash_cooldown
        self.velocity_x = Config.dash_speed * direction
        self.facing = direction
        spawn_particles(self.rect.centerx, self.rect.centery, cyan, count=10, spread=5)

    # ----- One frame of movement: timers, powers, jump physics, collision, animation -----
    def update(self, solids):
        self.frame_count += 1
        self._tick_timers()
        if not self._apply_fly_power():
            self._apply_jump_and_gravity()   # while flying there is no gravity
        self._animate_squash()
        self._move_and_collide(solids)
        self._animate_walk()

    def _tick_timers(self):
        if self.invincibility_timer > 0:
            self.invincibility_timer -= 1
        if self.punch_timer > 0:
            self.punch_timer -= 1
        if self.dash_cooldown > 0:
            self.dash_cooldown -= 1
        if self.power_timer > 0:
            self.power_timer -= 1
            if self.power_timer == 0:
                self.power = None
        if self.dashing:
            self.dash_timer -= 1
            if self.dash_timer <= 0:
                self.dashing = False
            spawn_dash_trail(self.rect.x, self.rect.y, self.facing)

    def _apply_fly_power(self):
        """Fly power (same as the HTML game): no gravity. Mario rises while UP / SPACE / W is held, sinks while
        DOWN / S is held and hovers otherwise. Returns True while the power is active.

        (It used to push up by 0.5 per frame while gravity pulled down by 0.75, so Mario never rose at all.)
        """
        if self.power != "fly":
            return False
        self.velocity_y = self.fly_input * Config.fly_speed
        self.jumps_left = 2
        self.jump_held = False
        return True

    def _apply_jump_and_gravity(self):
        """Variable jump height plus gravity (stronger on the way down, so jumps feel snappy)."""
        if self.jump_held:
            # Holding jump keeps the full upward speed for a limited number of frames.
            self.jump_frames += 1
            if self.jump_frames > Config.jump_hold_frames:
                self.jump_held = False
        elif self.velocity_y < 0:
            # Released early: damp the rise so a short tap gives a short hop.
            self.velocity_y *= Config.jump_release_damping

        falling = self.velocity_y > 0
        gravity = Config.gravity * Config.fall_gravity_multiplier if falling else Config.gravity
        self.velocity_y = min(self.velocity_y + gravity, Config.max_fall_speed)

    def _animate_squash(self):
        """Squash-and-stretch of the sprite; a landing puff of dust when touching the ground."""
        self.squash *= Config.squash_decay
        if abs(self.squash) < 0.02:
            self.squash = 0.0
        if not self.was_on_ground and self.on_ground:
            self.squash = Config.squash_on_landing
            spawn_particles(
                self.rect.centerx,
                self.rect.bottom,
                (180, 180, 180),
                count=5,
                spread=4,
                upward=False,
            )
        self.was_on_ground = self.on_ground

    def _move_and_collide(self, solids):
        """Move through the world. Landing refills the double jump; hitting a wall cancels a dash."""
        move_result = move_with_collision(self, solids)
        self.on_ground = move_result.on_ground
        if move_result.on_ground:
            self.jumps_left = 2
        if move_result.hit_wall_left or move_result.hit_wall_right:
            self.dashing = False

    def _animate_walk(self):
        if self.velocity_x != 0 and self.on_ground:
            self.walk_timer += 1
            if self.walk_timer >= 5:
                self.walk_timer = 0
                self.walk_frame = 1 - self.walk_frame
            self.idle_timer = 0
        else:
            self.walk_timer = 0
            self.walk_frame = 0
            if self.on_ground:
                self.idle_timer += 1

    def _draw_body(self, surface, x, y, clip_bottom=None):
        squash_amount = self.squash
        scale_x = 1.0 + squash_amount * 0.25
        scale_y = 1.0 - squash_amount * 0.25
        offset_x = int((32 * scale_x - 32) / 2)
        bob = self.walk_frame if (self.on_ground and self.velocity_x != 0) else 0
        idle_frames = self.idle_timer
        look_offset = (1 if (idle_frames // 20) % 2 == 0 else -1) if idle_frames > 120 else 0
        foot_tap = 1 if (idle_frames > 60 and idle_frames % 40 < 20) else 0
        facing_right = self.facing == 1
        palette = dash_palette if self.dashing else normal_palette

        def fill_rect(color, rect_x, rect_y, rect_width, rect_height):
            rect_y = int(rect_y)
            if clip_bottom is not None and rect_y >= clip_bottom:
                return
            clipped_height = (
                min(rect_height, clip_bottom - rect_y) if clip_bottom is not None else rect_height
            )
            if clipped_height <= 0:
                return
            draw_rect(
                surface,
                color,
                int(rect_x) - offset_x,
                rect_y,
                max(1, int(rect_width * scale_x)),
                max(1, int(clipped_height * scale_y)),
            )

        def fill_circle(color, center_x, center_y, radius):
            if clip_bottom is not None and center_y >= clip_bottom:
                return
            draw_circle(
                surface,
                color,
                int(center_x) - offset_x,
                int(center_y),
                max(1, int(radius * scale_x)),
            )

        hat_color = palette["hat"]
        skin_color = palette["skin"]
        overalls_color = palette["overalls"]
        shirt_color = palette["shirt"]
        boot_color = palette["boot"]
        mustache_color = palette["mustache"]
        hair_color = palette["hair"]
        button_color = palette["button"]
        shadow_color = palette["shadow"]

        fill_rect(boot_color, x + 3, y + 30 + bob + foot_tap, 10, 8)
        fill_rect(boot_color, x + 19, y + 30 + bob + foot_tap, 10, 8)
        fill_rect(black, x + 2, y + 34 + bob + foot_tap, 12, 4)
        fill_rect(black, x + 18, y + 34 + bob + foot_tap, 12, 4)
        fill_rect(overalls_color, x + 4, y + 20 + bob, 10, 12)
        fill_rect(overalls_color, x + 18, y + 20 + bob, 10, 12)
        fill_rect(overalls_color, x + 4, y + 12 + bob, 24, 10)
        fill_rect(shirt_color, x + 2, y + 14 + bob, 4, 8)
        fill_rect(shirt_color, x + 26, y + 14 + bob, 4, 8)
        fill_circle(skin_color, x + 3, y + 22 + bob, 3)
        fill_circle(skin_color, x + 29, y + 22 + bob, 3)
        fill_rect(overalls_color, x + 9, y + 10 + bob, 4, 4)
        fill_rect(overalls_color, x + 19, y + 10 + bob, 4, 4)
        fill_circle(button_color, x + 11, y + 13 + bob, 2)
        fill_circle(button_color, x + 21, y + 13 + bob, 2)
        fill_rect(skin_color, x + 13, y + 10 + bob, 6, 3)
        fill_rect(skin_color, x + 7, y + 4 + bob, 18, 9)
        fill_rect(shadow_color, x + 7, y + 11 + bob, 18, 2)
        fill_rect(skin_color, x + 5, y + 6 + bob, 3, 4)
        fill_rect(skin_color, x + 24, y + 6 + bob, 3, 4)
        fill_rect(hat_color, x + 7, y + bob, 18, 5)
        fill_rect(hat_color, x + 5, y + 4 + bob, 22, 3)
        fill_rect(hair_color, x + 5, y + 4 + bob, 3, 3)
        fill_rect(hair_color, x + 24, y + 4 + bob, 3, 3)
        fill_rect(tuple(min(channel + 30, 255) for channel in hat_color), x + 8, y + 1 + bob, 16, 1)
        if facing_right:
            fill_rect(white, x + 17 + look_offset, y + 5 + bob, 5, 4)
            fill_rect(black, x + 19 + look_offset, y + 6 + bob, 2, 2)
            fill_rect(mustache_color, x + 16, y + 4 + bob, 5, 1)
        else:
            fill_rect(white, x + 10 + look_offset, y + 5 + bob, 5, 4)
            fill_rect(black, x + 11 + look_offset, y + 6 + bob, 2, 2)
            fill_rect(mustache_color, x + 10, y + 4 + bob, 5, 1)
        nose_x = x + 19 if facing_right else x + 12
        fill_rect(shadow_color, nose_x, y + 8 + bob, 3, 2)
        fill_rect(mustache_color, x + 8, y + 11 + bob, 16, 2)
        fill_rect(mustache_color, x + 6, y + 10 + bob, 5, 3)
        fill_rect(mustache_color, x + 21, y + 10 + bob, 5, 3)
        fill_rect(mustache_color, x + 5, y + 11 + bob, 3, 2)
        fill_rect(mustache_color, x + 24, y + 11 + bob, 3, 2)

    def draw(self, screen, camera_x):
        if self.invincibility_timer > 0 and (self.invincibility_timer // 4) % 2 == 1:
            return  # blink while invincible
        clip_bottom = self._pipe_clip_bottom()
        x = self.rect.x - camera_x
        y = self.rect.y
        if self.active_character == "luigi":
            draw_luigi(screen, x, y, self.facing, self.walk_frame)
        elif self.active_character == "princess":
            draw_princess(screen, x, y - PRINCESS_SINK, self.walk_frame)
        elif self.active_character == "yoshi":
            draw_yoshi(screen, x, y, self.facing, self.walk_frame)
        else:
            if self.dashing or abs(self.velocity_x) >= Config.player_speed:
                self._draw_speed_ghost(screen, x, y)
            self._draw_body(screen, x, y, clip_bottom)
        if clip_bottom is None:
            self._draw_punch_fist(screen, x, y)
            self._draw_shadow(screen, x)

    def _pipe_clip_bottom(self):
        """While sinking into a pipe only the part above this line is drawn (None = draw everything)."""
        if self.pipe_sink_timer <= 0:
            return None
        sunk = 1.0 - self.pipe_sink_timer / Config.pipe_sink_frames
        return int(self.pipe_sink_start_y + Config.player_height * (1.0 - sunk))

    def _draw_speed_ghost(self, screen, x, y):
        ghost = pygame.Surface((46, 46), pygame.SRCALPHA)
        self._draw_body(ghost, 8, 4, None)
        ghost.set_alpha(70)
        screen.blit(ghost, (x - self.facing * 10 - 8, y - 4))

    def _draw_punch_fist(self, screen, x, y):
        if self.punch_timer <= 0:
            return
        reach = 22 if self.punch_timer > Config.punch_duration // 2 else 14
        fist_x = x + (32 if self.facing > 0 else -reach)
        pygame.draw.circle(screen, skin, (int(fist_x), int(y + 20)), 6)
        pygame.draw.rect(screen, red, (int(fist_x - 4), int(y + 16), 8, 5))

    def _draw_shadow(self, screen, x):
        shadow_offset_x = int((32 * (1.0 + self.squash * 0.25) - 32) / 2)
        shadow_surface = pygame.Surface((28, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surface, (0, 0, 0, 55), (0, 0, 28, 6))
        screen.blit(shadow_surface, (x + 2 - shadow_offset_x, self.rect.bottom))