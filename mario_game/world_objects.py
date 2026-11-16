"""Things placed in the level: Lucky Blocks, Pipes and Checkpoints."""
import math
import pygame
from settings import (
    Config, black, white, green, dark_green, light_green, light_gray, pipe_green, pipe_dark_green, gold,
)
from utils import draw_rect


class LuckyBlock:
    width = height = Config.tile_size

    def __init__(self, world_x, world_y, reward):
        self.rect = pygame.Rect(world_x, world_y, self.width, self.height)
        self.used = False; self.animation_timer = 0; self.bump_timer = 0; self.coin_pop_timer = 0
        self.reward = reward          # always given by the level generator (see level.build_level)

    def try_hit(self):
        """Activate the block when hit from any side (top, bottom or sides)."""
        if self.used: return False
        self.used = True; self.bump_timer = 8; self.coin_pop_timer = 30
        return True

    def update(self):
        self.animation_timer = (self.animation_timer+1) % 60
        if self.bump_timer > 0: self.bump_timer -= 1
        if self.coin_pop_timer > 0: self.coin_pop_timer -= 1

    def draw(self, screen, camera_x, font):
        screen_x = self.rect.x - camera_x; screen_y = self.rect.y - self.bump_timer//2
        block_color = (150,108,40) if self.used else (255,180,30)
        draw_rect(screen, block_color, screen_x, screen_y, self.width, self.height)
        pygame.draw.rect(screen, (120,80,20) if self.used else gold, (screen_x,screen_y,self.width,self.height), 3)
        if not self.used:
            question_color = (255,240,0) if (self.animation_timer//10)%2==0 else white
            question_mark = font.render("?", True, question_color)
            screen.blit(question_mark, question_mark.get_rect(center=(screen_x+self.width//2, screen_y+self.height//2)))
        if self.coin_pop_timer > 0:
            progress = self.coin_pop_timer / 30.0
            coin_y = screen_y - int(40*progress)
            pygame.draw.ellipse(screen, gold, (screen_x+10, coin_y, 12, 16))
            pygame.draw.ellipse(screen, (255,240,150), (screen_x+13, coin_y+3, 6, 10))


class Pipe:
    width=52; height=80; lip_height=18; lip_extension=8

    def __init__(self, world_x, ground_y):
        self.world_x = world_x; self.world_y = ground_y - self.height
        shaft_top = self.world_y + self.lip_height
        self.shaft = pygame.Rect(world_x, shaft_top, self.width, ground_y - shaft_top)
        # Only the part of the lip right above the pipe body is solid (and deadly to land on).
        # The overhang that sticks out past the body on each side is just decoration: Mario passes through it.
        self.lip_center = pygame.Rect(world_x, self.world_y, self.width, self.lip_height)

    def draw(self, screen, camera_x):
        screen_x = self.world_x - camera_x; screen_y = self.world_y
        draw_rect(screen,pipe_green,  screen_x+4,      screen_y+self.lip_height, self.width-8, self.height-self.lip_height)
        draw_rect(screen,pipe_dark_green, screen_x+4,      screen_y+self.lip_height, 8,        self.height-self.lip_height)
        draw_rect(screen,light_green,screen_x+self.width-12,screen_y+self.lip_height,6,       self.height-self.lip_height)
        draw_rect(screen,pipe_green,  screen_x-self.lip_extension,screen_y,         self.width+self.lip_extension*2,self.lip_height)
        draw_rect(screen,pipe_dark_green, screen_x-self.lip_extension,screen_y,         6,        self.lip_height)
        draw_rect(screen,light_green,screen_x+self.width+2,screen_y,        4,        self.lip_height)
        pygame.draw.rect(screen,dark_green,(screen_x,screen_y,self.width,self.height),2)


class Checkpoint:
    def __init__(self, world_x, ground_y):
        self.world_x = world_x; self.world_y = ground_y - 72
        self.rect = pygame.Rect(world_x, ground_y-72, 10, 72)
        self.activated = False; self.animation_timer = 0

    def update(self): self.animation_timer = (self.animation_timer+1) % 60

    def draw(self, screen, camera_x):
        screen_x = self.world_x - camera_x; screen_y = self.world_y
        draw_rect(screen, gold if self.activated else light_gray, screen_x+2, screen_y, 6, self.rect.h)
        pygame.draw.rect(screen, black, (screen_x+2, screen_y, 6, self.rect.h), 1)
        if self.activated:
            pulse = abs(math.sin(self.animation_timer*.1))
            flag_color = (int(255*pulse), int(160*(1-pulse)), 0)
        else:
            flag_color = green
        pygame.draw.polygon(screen, flag_color, [(screen_x+8,screen_y),(screen_x+30,screen_y+10),(screen_x+8,screen_y+20)])
