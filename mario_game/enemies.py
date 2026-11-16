"""Enemies: the Mushroom walker and the Turtle boss."""
import math
import pygame
from settings import (
    Config, black, white, red, dark_red, green, dark_green, orange,
)
from utils import draw_rect, draw_circle, draw_line, move_with_collision, ground_ahead, wall_ahead


class Mushroom:
    def __init__(self, world_x, world_y, patrol_range=Config.enemy_patrol_range):
        self.rect     = pygame.Rect(world_x, world_y, 32, 30)
        self.start_x  = world_x; self.patrol_range = patrol_range
        self.direction      = 1; self.speed = Config.enemy_speed
        self.animation_timer       = 0; self.alive = True; self.squish = 0
        self.velocity_x       = 0.0; self.velocity_y = 0.0; self.subpixel_x = 0.0; self.subpixel_y = 0.0

    def update(self, solids, terrain_solids=None):
        if self.squish > 0: self.squish -= 1; return
        if terrain_solids is None:
            terrain_solids = solids

        self.velocity_y = min(self.velocity_y + Config.enemy_gravity, Config.max_fall_speed)
        self.velocity_x = self.speed * self.direction
        move_result = move_with_collision(self, solids, clamp_left=False)
        if move_result.on_ground: self.velocity_y = 0

        self.animation_timer = (self.animation_timer+1) % 30

        # Turn around at ledges and walls (only while standing, so it doesn't flip mid-air).
        if move_result.on_ground:
            no_ground = not ground_ahead(self.rect, terrain_solids, self.direction)
            hit_wall  = wall_ahead(self.rect, terrain_solids, self.direction)
            if no_ground or hit_wall or move_result.hit_wall_left or move_result.hit_wall_right:
                self.direction *= -1

        # Never wander farther than the patrol range from the spawn point.
        if self.rect.x > self.start_x + self.patrol_range: self.direction = -1
        elif self.rect.x < self.start_x - 10:        self.direction =  1

    def draw(self, screen, camera_x):
        x = self.rect.x - camera_x; y = self.rect.y
        if self.squish > 0:
            draw_rect(screen,(160,40,40),x,y+20,32,10)
            draw_rect(screen,(100,20,20),x,y+22,32,6); return
        bob = 1 if self.animation_timer < 15 else 0
        pygame.draw.ellipse(screen,(180,40,40),(x,y+bob,32,18))
        pygame.draw.ellipse(screen,(210,70,70),(x+3,y+bob+1,26,10))
        draw_circle(screen,white,x+9,y+5+bob,3); draw_circle(screen,white,x+20,y+5+bob,4)
        draw_rect(screen,(235,190,130),x+5,y+14+bob,22,14)
        draw_rect(screen,(200,155,100),x+5,y+24+bob,22,4)
        draw_circle(screen,black,x+11,y+19+bob,3); draw_circle(screen,black,x+21,y+19+bob,3)
        draw_line(screen,black,x+8,y+14+bob,x+14,y+16+bob)
        draw_line(screen,black,x+18,y+16+bob,x+24,y+14+bob)
        left_foot_lift = -2 if self.animation_timer < 15 else 0; right_foot_lift = 0 if self.animation_timer < 15 else -2
        pygame.draw.ellipse(screen,(70,35,5),(x+2,y+26+left_foot_lift,12,8))
        pygame.draw.ellipse(screen,(70,35,5),(x+18,y+26+right_foot_lift,12,8))


class Turtle:
    def __init__(self, world_x, world_y, health=5, final=False, variant="normal"):
        self.rect   = pygame.Rect(world_x, world_y, 80, 80)
        self.health     = health; self.max_health = health
        self.direction    = -1; self.speed  = 2 + health//4
        self.animation_timer     = 0;  self.alive  = True
        self.final  = final; self.variant = variant; self.hurt = 0
        self.velocity_x     = 0.0; self.velocity_y = 0.0; self.subpixel_x = 0.0; self.subpixel_y = 0.0
        self.attack_cooldown = 70
        self.projectiles = []
        # The fight zone: the boss lives in the last part of the level and never walks out of it.
        self.arena_left = Config.level_width - Config.boss_arena_width
        self.arena_right = Config.level_width

    def update(self, player_x, platforms):
        self.animation_timer = (self.animation_timer+1) % 60
        if self.hurt > 0: self.hurt -= 1

        self.velocity_y  = min(self.velocity_y + 0.6, Config.max_fall_speed)
        self.direction = 1 if player_x > self.rect.centerx else -1
        self.velocity_x  = self.speed * self.direction
        # `platforms` is the full list of solids (pipes and blocks too), so an obstacle stops the boss.
        move_with_collision(self, platforms, clamp_left=False, world_right=self.arena_right)
        if self.rect.left < self.arena_left:
            self.rect.left = self.arena_left
            self.velocity_x = 0; self.subpixel_x = 0
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
        elif abs(player_x-self.rect.x) < 520:
            origin_x = self.rect.centerx; origin_y = self.rect.y+25
            delta_x = player_x-origin_x; delta_y = Config.ground_y-30-origin_y
            distance = max(1.0, math.hypot(delta_x, delta_y))
            self.projectiles.append({
                "x":float(origin_x), "y":float(origin_y),
                "velocity_x":delta_x/distance*7, "velocity_y":delta_y/distance*7-4,
                "life":120, "variant":self.variant
            })
            self.attack_cooldown = 90
        for shell in self.projectiles[:]:
            shell["x"] += shell["velocity_x"]; shell["y"] += shell["velocity_y"]
            shell["velocity_y"] += 0.3; shell["life"] -= 1
            if shell["life"] <= 0 or shell["y"] > Config.ground_y:
                self.projectiles.remove(shell)

    def take_damage(self):
        self.health -= 1; self.hurt = 20; return self.health <= 0

    def draw(self, screen, camera_x):
        if self.hurt > 0 and (self.hurt//3) % 2 == 1: return
        x = self.rect.x - camera_x; y = self.rect.y
        bob = int(2 * abs(math.sin(self.animation_timer*0.1)))
        palettes = {
            "normal": ((0,130,50), (0,180,80), green),
            "space": ((40,55,150), (80,130,255), (80,170,255)),
            "lava": ((125,35,10), (235,75,15), orange),
            "undead": ((75,65,85), (150,140,170), (180,180,195)),
        }
        shell_dark_color, shell_light_color, head_color = palettes.get(self.variant, palettes["normal"])
        pygame.draw.ellipse(screen,shell_dark_color,(x,y+bob,80,60))
        pygame.draw.ellipse(screen,shell_light_color,(x+6,y+6+bob,68,40))
        for column in range(3):
            for row in range(2):
                draw_circle(screen,shell_dark_color,x+18+column*22,y+15+row*18+bob,8)
                pygame.draw.circle(screen,black,(int(x+18+column*22),int(y+15+row*18+bob)),8,2)
        head_x = x-18 if self.direction<0 else x+70
        pygame.draw.ellipse(screen,head_color,(head_x,y+22+bob,28,30))
        eye_x = head_x+6 if self.direction<0 else head_x+16
        draw_circle(screen,white,eye_x,y+32+bob,6); draw_circle(screen,black,eye_x,y+32+bob,3)
        draw_circle(screen,white,eye_x+1,y+30+bob,2)
        pygame.draw.ellipse(screen,head_color,(x+6,y+55+bob,22,14))
        pygame.draw.ellipse(screen,head_color,(x+52,y+55+bob,22,14))
        bar_width=100; bar_x=x+(80-bar_width)//2; bar_y=y-24
        draw_rect(screen,dark_red,bar_x,bar_y,bar_width,12)
        health_width = int(self.health/self.max_health*bar_width)
        health_color = green if self.health>self.max_health*0.6 else orange if self.health>2 else red
        draw_rect(screen,health_color,bar_x,bar_y,health_width,12)
        segment_width = bar_width/self.max_health
        for segment_index in range(1,self.max_health):
            divider_x = int(bar_x+segment_index*segment_width); draw_line(screen,black,divider_x,bar_y,divider_x,bar_y+12,1)
        pygame.draw.rect(screen,black,(int(bar_x),int(bar_y),bar_width,12),2)

    def draw_projectiles(self, screen, camera_x):
        for shell in self.projectiles:
            x = int(shell["x"]-camera_x); y = int(shell["y"])
            color = {"lava": (220,55,15), "space": (80,120,230),
                     "undead": (160,160,180)}.get(shell.get("variant"), dark_green)
            pygame.draw.ellipse(screen,color,(x-10,y-8,20,16))
            pygame.draw.ellipse(screen,white,(x-5,y-5,5,4))
