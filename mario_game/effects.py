"""Visual effects: the falling title letters and the particle system."""
import random
import pygame
from settings import Config, cyan


class FallingLetters:
    def __init__(self, text, color, font, y_target=240, delay=5):
        self.letters = []
        total_width = sum(font.size(character)[0] for character in text) + (len(text)-1)*4
        letter_x = Config.screen_width//2 - total_width//2
        for index, character in enumerate(text):
            character_width, _ = font.size(character)
            self.letters.append({"character":character,"x":letter_x,"y":float(-80-index*28),
                                  "velocity_y":0.0,"target":float(y_target),
                                  "done":False,"color":color,"font":font})
            letter_x += character_width + 4
        self.delay = delay; self.timer = 0; self.active_letter_count = 0

    def update(self):
        self.timer += 1
        if self.timer >= self.delay:
            self.timer = 0
            if self.active_letter_count < len(self.letters): self.active_letter_count += 1
        for letter in self.letters[:self.active_letter_count]:
            if letter["done"]: continue
            letter["velocity_y"] += Config.gravity * 0.9; letter["y"] += letter["velocity_y"]
            if letter["y"] >= letter["target"]:
                letter["y"] = letter["target"]; letter["velocity_y"] *= -0.38
                if abs(letter["velocity_y"]) < 1.2: letter["done"] = True

    def draw(self, screen):
        for letter in self.letters:
            letter_surface = letter["font"].render(letter["character"], True, letter["color"])
            screen.blit(letter_surface, (int(letter["x"]), int(letter["y"])))

    @property
    def finished(self): return all(letter["done"] for letter in self.letters)


class Particle:
    __slots__ = ('x','y','velocity_x','velocity_y','color','life','max_life','size')
    def __init__(self, x, y, velocity_x, velocity_y, color, life=20, size=4):
        self.x=x; self.y=y; self.velocity_x=velocity_x; self.velocity_y=velocity_y
        self.color=color; self.life=life; self.max_life=life; self.size=size
    def update(self):
        self.x+=self.velocity_x; self.y+=self.velocity_y; self.velocity_y+=0.3; self.life-=1
    @property
    def alive(self): return self.life > 0
    def draw(self, screen, camera_x):
        draw_size = max(1, int(self.size * self.life / self.max_life))
        pygame.draw.rect(screen, self.color, (int(self.x-camera_x), int(self.y), draw_size, draw_size))


# Shared list of live particles. Other modules import this exact list, so always change it
# in place (clear() / slice assignment) and never rebind it to a new list.
particles = []


def spawn_particles(x, y, color, count=6, spread=3, upward=True):
    for _ in range(count):
        velocity_x = random.uniform(-spread, spread)
        velocity_y = random.uniform(-4, -1) if upward else random.uniform(-1, 2)
        particles.append(Particle(x, y, velocity_x, velocity_y, color,
                                  life=random.randint(15,30),
                                  size=random.randint(3,6)))


def spawn_dash_trail(x, y, facing):
    for index in range(4):
        offset_x = (index*6) * (-1 if facing == 1 else 1)
        particles.append(Particle(x+offset_x, y+random.randint(0,30),
                                  random.uniform(-1,1), random.uniform(-0.5,0.5),
                                  cyan, life=12, size=5))
