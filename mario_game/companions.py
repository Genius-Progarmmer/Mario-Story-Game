"""AI followers (Luigi, Princess, Yoshi) that trail behind Mario."""
import math
import pygame
from settings import Config
from utils import move_with_collision, ground_ahead, wall_ahead
from sprites import draw_luigi, draw_princess, draw_yoshi
from player import Mario


class Companion:
    """AI follower matching the HTML game's Luigi/Princess/Yoshi team."""
    def __init__(self, x, y, kind, offset):
        self.rect=pygame.Rect(x,y,32,38)
        self.velocity_x=0.0; self.velocity_y=0.0; self.subpixel_x=0.0; self.subpixel_y=0.0
        self.kind=kind; self.offset=offset; self.facing=1
        self.on_ground=False; self.frame=0; self.walk_timer=0
        # What this team member LOOKS like. It starts as its own kind; when the player switches hero the two swap
        # looks (see Game._cycle_character), so the same character is never drawn twice.
        self.appearance=kind
        self._mario_sprite=None

    def update(self, mario, solids):
        target_x=mario.rect.x-self.offset
        delta_x=target_x-self.rect.x
        distance=abs(delta_x)
        if distance>Config.companion_far_distance:
            self.velocity_x=math.copysign(Config.companion_speed,delta_x)
        elif distance>Config.companion_near_distance:
            self.velocity_x=math.copysign(Config.companion_speed*.6,delta_x)
        else:
            self.velocity_x=delta_x*.08
        if abs(self.velocity_x)>.2: self.facing=1 if self.velocity_x>0 else -1

        direction=1 if self.velocity_x>0 else -1 if self.velocity_x<0 else 0
        if direction and (not ground_ahead(self.rect,solids,direction)
                          or wall_ahead(self.rect,solids,direction)):
            self.velocity_x=0
            if self.on_ground: self.velocity_y=Config.companion_jump_speed
        if self.on_ground and mario.rect.y < self.rect.y-60 and distance<200:
            self.velocity_y=Config.companion_jump_speed

        self.velocity_y=min(self.velocity_y+Config.companion_gravity,Config.max_fall_speed)
        result=move_with_collision(self,solids)
        self.on_ground=result.on_ground
        if self.on_ground: self.velocity_y=0
        if (result.hit_wall_left or result.hit_wall_right) and self.on_ground:
            self.velocity_y=Config.companion_jump_speed
        if abs(self.velocity_x)>.5 and self.on_ground:
            self.walk_timer=(self.walk_timer+1)%12
            self.frame=1 if self.walk_timer<6 else 0
        else:
            self.frame=0

    def draw(self, screen, camera_x):
        x=self.rect.x-camera_x; y=self.rect.y
        if self.appearance=="mario":
            self._draw_as_mario(screen,x,y)
        elif self.appearance=="luigi":
            draw_luigi(screen,x,y,self.facing,self.frame)
        elif self.appearance=="yoshi":
            draw_yoshi(screen,x,y,self.facing,self.frame)
        else:
            draw_princess(screen,x,y,self.frame)

    def _draw_as_mario(self, screen, x, y):
        """Mario's sprite is drawn by Mario itself, so a stand-in Mario (never updated, only drawn) is used."""
        if self._mario_sprite is None:
            self._mario_sprite=Mario(0,0)
        sprite=self._mario_sprite
        sprite.facing=self.facing; sprite.walk_frame=self.frame
        sprite.on_ground=self.on_ground; sprite.velocity_x=self.velocity_x
        sprite._draw_body(screen,x,y)
