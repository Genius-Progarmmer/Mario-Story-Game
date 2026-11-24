"""AI followers (Luigi, Princess, Yoshi) that trail behind Mario."""
import math
import pygame
from settings import Config
from utils import move_with_collision, ground_ahead, wall_ahead
from sprites import draw_luigi, draw_princess, draw_yoshi, PRINCESS_SINK
from player import Mario


class Companion:
    """AI follower matching the HTML game's Luigi/Princess/Yoshi team."""
    def __init__(self, x, y, kind, offset):
        self.rect=pygame.Rect(x,y,32,38)
        self.velocity_x=0.0; self.velocity_y=0.0; self.subpixel_x=0.0; self.subpixel_y=0.0
        self.kind=kind; self.offset=offset; self.facing=1
        self.on_ground=False; self.frame=0; self.walk_timer=0
        self.jumps_left=3
        self.clearing=False; self.clear_direction=1; self.clear_start_y=0
        # What this team member LOOKS like. It starts as its own kind; when the player switches hero the two swap
        # looks (see Game._cycle_character), so the same character is never drawn twice.
        self.appearance=kind
        self._mario_sprite=None

    # ----- AI: follow Mario, and get over pipes / walls / gaps like the HTML game's team -----
    def _on_pipe_rim(self, pipes):
        """Is this team member standing on the top of a pipe?"""
        for pipe in pipes:
            rim = pipe.lip_center
            if (self.rect.right > rim.left and self.rect.left < rim.right
                    and abs(self.rect.bottom - rim.top) < 4):
                return True
        return False

    def _start_clearing(self, direction):
        """Jump up first, and only walk forward once the jump has lifted the body above the obstacle."""
        self.velocity_y = Config.companion_jump_speed
        self.jumps_left = 2
        self.clearing = True
        self.clear_direction = direction
        self.clear_start_y = self.rect.y

    def _next_jump_speed(self):
        return Config.companion_jump_speed_2 if self.jumps_left == 2 else Config.companion_jump_speed_3

    def update(self, mario, solids, pipes=()):
        target_x = mario.rect.x - self.offset
        delta_x = target_x - self.rect.x
        distance = abs(delta_x)
        toward = 1 if delta_x > 0 else -1 if delta_x < 0 else self.facing
        if distance > Config.companion_far_distance:
            self.velocity_x = toward * Config.companion_speed
        elif distance > Config.companion_near_distance:
            self.velocity_x = toward * Config.companion_speed * .6
        else:
            self.velocity_x = delta_x * .08

        # Climbing over an obstacle: stand still until the jump has risen high enough, then go forward at full speed.
        # (It used to stop moving AND jump, so it hopped on the spot in front of a pipe for ever.)
        if self.clearing:
            risen = self.clear_start_y - self.rect.y
            self.velocity_x = self.clear_direction * Config.companion_speed if risen > Config.companion_clear_rise else 0
        # Standing on a pipe's rim: keep walking, the way down is on the other side.
        if self.on_ground and not self.clearing and self._on_pipe_rim(pipes):
            self.velocity_x = toward * Config.companion_speed * .6
        if abs(self.velocity_x) > .2:
            self.facing = 1 if self.velocity_x > 0 else -1

        direction = 1 if self.velocity_x > 0 else -1 if self.velocity_x < 0 else 0
        if direction:
            if self.on_ground and not self.clearing:
                no_floor = not ground_ahead(self.rect, solids, direction)
                wall = wall_ahead(self.rect, solids, direction, Config.companion_wall_look_ahead)
                if no_floor or wall:
                    self._start_clearing(direction)
            elif self.jumps_left > 0 and self.velocity_y > -2:
                if wall_ahead(self.rect, solids, direction):   # still blocked in the air: use the next jump
                    self.velocity_y = self._next_jump_speed()
                    self.jumps_left -= 1
        if self.on_ground and mario.rect.y < self.rect.y - 60 and distance < 200:
            self.velocity_y = Config.companion_jump_speed       # Mario is on a higher level: jump up to him

        self.velocity_y = min(self.velocity_y + Config.companion_gravity, Config.max_fall_speed)
        result = move_with_collision(self, solids)
        self.on_ground = result.on_ground
        if self.on_ground:
            self.velocity_y = 0
            if self.clearing and self._on_pipe_rim(pipes) and self.jumps_left > 0:
                # landed on top of the pipe: jump again, from the rim, to get down on the far side
                self.velocity_y = self._next_jump_speed()
                self.jumps_left -= 1
                self.clear_start_y = self.rect.y
            else:
                self.jumps_left = 3
                self.clearing = False
        if (result.hit_wall_left or result.hit_wall_right) and self.on_ground:
            self._start_clearing(1 if result.hit_wall_right else -1)
        if abs(self.velocity_x) > .5 and self.on_ground:
            self.walk_timer = (self.walk_timer + 1) % 12
            self.frame = 1 if self.walk_timer < 6 else 0
        else:
            self.frame = 0

    def draw(self, screen, camera_x):
        x=self.rect.x-camera_x; y=self.rect.y
        if self.appearance=="mario":
            self._draw_as_mario(screen,x,y)
        elif self.appearance=="luigi":
            draw_luigi(screen,x,y,self.facing,self.frame)
        elif self.appearance=="yoshi":
            draw_yoshi(screen,x,y,self.facing,self.frame)
        else:
            draw_princess(screen,x,y-PRINCESS_SINK,self.frame)

    def _draw_as_mario(self, screen, x, y):
        """Mario's sprite is drawn by Mario itself, so a stand-in Mario (never updated, only drawn) is used."""
        if self._mario_sprite is None:
            self._mario_sprite=Mario(0,0)
        sprite=self._mario_sprite
        sprite.facing=self.facing; sprite.walk_frame=self.frame
        sprite.on_ground=self.on_ground; sprite.velocity_x=self.velocity_x
        sprite._draw_body(screen,x,y)