"""Hand-drawn sprites: hearts and the Princess / Luigi / Yoshi characters."""
import math
import pygame
from settings import (
    black, white, red, skin, pink, light_pink, gold,
)
from utils import draw_rect, draw_circle


def draw_heart(surface, center_x, center_y, size=13, color=red, beat=0.0):
    scaled_size = size * (1.0 + beat * 0.2)
    points = []
    for index in range(64):
        angle = math.pi * 2 * index / 64
        x = 16 * math.sin(angle) ** 3
        y = -(13*math.cos(angle) - 5*math.cos(2*angle) - 2*math.cos(3*angle) - math.cos(4*angle))
        points.append((int(center_x + x*scaled_size/16), int(center_y + y*scaled_size/16)))
    pygame.draw.polygon(surface, color, points)
    highlight_points = [(int(center_x-2 + (16*math.sin(math.pi*2*index/32)**3)*scaled_size*0.38/16),
           int(center_y-3 - (13*math.cos(math.pi*2*index/32) - 5*math.cos(2*math.pi*2*index/32)
                       - 2*math.cos(3*math.pi*2*index/32) - math.cos(4*math.pi*2*index/32))*scaled_size*0.38/16))
          for index in range(32)]
    if len(highlight_points) >= 3:
        pygame.draw.polygon(surface, (255, 110, 130), highlight_points)


# The Princess sprite is taller than a Mario-sized body: her shoes are drawn 25px below the body rectangle's bottom.
# Callers that draw her on a character's rectangle subtract this, so she stands ON the ground instead of sinking into it.
PRINCESS_SINK = 25


def draw_princess(screen, x, y, frame=0):
    bob = int(math.sin(frame*.08)*3)
    pygame.draw.polygon(screen,pink,[(x+12,y+22+bob),(x+2,y+60+bob),(x+30,y+60+bob),(x+20,y+22+bob)])
    pygame.draw.polygon(screen,light_pink,[(x+12,y+22+bob),(x+6,y+55+bob),(x+16,y+55+bob)])
    for crown_tip_x,crown_tip_y in [(x+7,y+bob-2),(x+11,y+bob-4),(x+15,y+bob-2)]:
        pygame.draw.polygon(screen,gold,[(crown_tip_x-3,y+bob+2),(crown_tip_x,crown_tip_y),(crown_tip_x+3,y+bob+2)])
    draw_rect(screen,gold,x+5,y+bob+2,22,4)
    draw_circle(screen,skin,x+16,y+14+bob,11)
    draw_rect(screen,gold,x+5,y+3+bob,22,12); draw_rect(screen,gold,x+4,y+14+bob,5,8); draw_rect(screen,gold,x+23,y+14+bob,5,8)
    draw_circle(screen,(100,50,200),x+12,y+14+bob,2); draw_circle(screen,(100,50,200),x+20,y+14+bob,2)
    pygame.draw.arc(screen,red,(x+11,y+18+bob,10,5),math.pi,0,2)
    draw_rect(screen,skin,x+3,y+24+bob,8,5); draw_rect(screen,skin,x+21,y+24+bob,8,5)
    pygame.draw.ellipse(screen,red,(x+5,y+57+bob,10,6))
    pygame.draw.ellipse(screen,red,(x+17,y+57+bob,10,6))


def draw_luigi(screen, x, y, facing=1, frame=0):
    """Standalone Luigi sprite used by the Python companion system."""
    bob = 1 if frame else 0
    pygame.draw.ellipse(screen, (40, 40, 40), (x+2, y+33, 28, 6))
    draw_rect(screen, (30, 130, 50), x+5, y+17+bob, 22, 15)
    draw_rect(screen, (20, 75, 150), x+7, y+25+bob, 18, 10)
    draw_circle(screen, skin, x+16, y+11+bob, 11)
    draw_rect(screen, (30, 150, 55), x+3, y+3+bob, 26, 8)
    draw_rect(screen, (30, 150, 55), x+1, y+9+bob, 30, 5)
    draw_circle(screen, white, x+12, y+10+bob, 3)
    draw_circle(screen, white, x+21, y+10+bob, 3)
    draw_circle(screen, black, x+13, y+10+bob, 1)
    draw_circle(screen, black, x+22, y+10+bob, 1)
    draw_rect(screen, (80, 40, 15), x+9, y+17+bob, 15, 4)
    draw_rect(screen, (90, 45, 15), x+2, y+34, 11, 5)
    draw_rect(screen, (90, 45, 15), x+19, y+34, 11, 5)


def draw_yoshi(screen, x, y, facing=1, frame=0):
    """Simple animated Yoshi sprite for the standalone Python build."""
    bob = 1 if frame else 0
    pygame.draw.ellipse(screen, (0, 0, 0), (x+2, y+34, 30, 5))
    pygame.draw.ellipse(screen, (50, 180, 80), (x+5, y+12+bob, 24, 24))
    pygame.draw.ellipse(screen, (90, 220, 100), (x+13, y+4+bob, 20, 18))
    pygame.draw.ellipse(screen, (240, 240, 220), (x+18, y+10+bob, 12, 8))
    draw_circle(screen, black, x+23, y+12+bob, 2)
    pygame.draw.polygon(screen, (220, 50, 40),
                        [(x+28, y+17+bob), (x+38, y+21+bob),
                         (x+28, y+25+bob)])
    draw_rect(screen, (220, 40, 35), x+6, y+3+bob, 12, 4)
    draw_rect(screen, white, x+10, y+7+bob, 5, 4)
    draw_rect(screen, (210, 40, 30), x+6, y+33, 10, 5)
    draw_rect(screen, (210, 40, 30), x+20, y+33, 10, 5)