"""Side-scrolling camera with screen shake."""
import random
from settings import Config


class Camera:
    def __init__(self): self.x=0.0; self.shake_strength=0

    def update(self, player_x):
        target_x = max(0.0, min(float(Config.level_width-Config.screen_width), float(player_x-Config.screen_width//2)))
        self.x += (target_x-self.x)*0.14
        if self.shake_strength > 0: self.shake_strength -= 1

    def shake(self, amount=5): self.shake_strength = amount

    @property
    def shake_offset_x(self):
        return random.randint(-self.shake_strength, self.shake_strength) if self.shake_strength>0 else 0
