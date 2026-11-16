"""Small drawing helpers and the collision code shared by every character."""
import pygame
from settings import Config


def draw_rect(surface, color, x, y, width, height):
    pygame.draw.rect(surface, color, (int(x), int(y), max(1, int(width)), max(1, int(height))))


def draw_circle(surface, color, x, y, radius):
    pygame.draw.circle(surface, color, (int(x), int(y)), max(1, int(radius)))


def draw_line(surface, color, start_x, start_y, end_x, end_y, line_width=1):
    pygame.draw.line(
        surface,
        color,
        (int(start_x), int(start_y)),
        (int(end_x), int(end_y)),
        line_width,
    )


class MoveResult:
    __slots__ = ("on_ground", "hit_ceiling", "hit_wall_left", "hit_wall_right")

    def __init__(self):
        self.on_ground = False
        self.hit_ceiling = False
        self.hit_wall_left = False
        self.hit_wall_right = False


def move_with_collision(entity, solids, clamp_left=True, world_right=None):
    """Shared two-phase movement and collision for every character.

    The caller decides an entity's velocity; this function is responsible for
    applying it safely.  Horizontal movement is resolved first, followed by
    vertical movement; both advance one pixel at a time.  Both phases use the
    same complete ``solids`` collection, so this routine does not treat
    platforms, pipes, or blocks differently.
    """
    if world_right is None:
        world_right = Config.level_width
    move_result = MoveResult()

    # Phase 1: horizontal move.
    # Speeds below one pixel per frame are not lost: the fraction is kept in subpixel_x and the
    # entity only moves once the pieces add up to a whole pixel.
    entity.subpixel_x = getattr(entity, "subpixel_x", 0.0) + entity.velocity_x
    steps_x = int(entity.subpixel_x)
    entity.subpixel_x -= steps_x
    step_direction_x = 1 if steps_x > 0 else -1

    # Move ONE pixel at a time and check for a wall after every pixel. Moving the whole distance at
    # once would let a fast entity (a dash) jump over a thin wall without ever overlapping it.
    for _ in range(abs(steps_x)):
        entity.rect.x += step_direction_x
        wall_index = entity.rect.collidelist(solids)
        if wall_index != -1:
            wall = solids[wall_index]
            if step_direction_x > 0:
                entity.rect.right = wall.left
                move_result.hit_wall_right = True
            else:
                entity.rect.left = wall.right
                move_result.hit_wall_left = True
            entity.velocity_x = 0
            entity.subpixel_x = 0
            break

    if clamp_left and entity.rect.left < 0:
        entity.rect.left = 0
        entity.velocity_x = 0
    if entity.rect.right > world_right:
        entity.rect.right = world_right
        entity.velocity_x = 0

    # Phase 2: vertical move, same idea: keep the fractional part, then step 1px at a time.
    # If the total is still under one pixel the entity simply does not move this frame.
    entity.subpixel_y = getattr(entity, "subpixel_y", 0.0) + entity.velocity_y
    steps_y = int(entity.subpixel_y)
    entity.subpixel_y -= steps_y
    step_direction_y = 1 if steps_y > 0 else -1

    for _ in range(abs(steps_y)):
        entity.rect.y += step_direction_y
        solid_index = entity.rect.collidelist(solids)
        if solid_index != -1:
            solid = solids[solid_index]
            if step_direction_y > 0:
                entity.rect.bottom = solid.top
                move_result.on_ground = True
            else:
                entity.rect.top = solid.bottom
                move_result.hit_ceiling = True
            entity.velocity_y = 0
            entity.subpixel_y = 0
            break

    # Standing still on something: look 1px below WITHOUT moving, so resting on the ground still
    # counts as on_ground now that tiny movements no longer force a whole-pixel step.
    if not move_result.on_ground and entity.velocity_y >= 0:
        if entity.rect.move(0, 1).collidelist(solids) != -1:
            move_result.on_ground = True
            entity.velocity_y = 0
            entity.subpixel_y = 0

    return move_result


def ground_ahead(rect, solids, direction_x):
    """Is there ground in front of the entity? (used to detect ledges)"""
    look_ahead = Config.companion_edge_look_ahead
    probe_x = rect.x + (rect.w + look_ahead if direction_x > 0 else -look_ahead - 2)
    probe = pygame.Rect(probe_x, rect.y + rect.h + 2, 2, 8)
    return any(probe.colliderect(solid) for solid in solids)


def wall_ahead(rect, solids, direction_x):
    """Is there a wall in front of the entity?"""
    probe_x = rect.x + (rect.w + 2 if direction_x > 0 else -10)
    probe = pygame.Rect(probe_x, rect.y + 4, 8, rect.h - 8)
    return any(probe.colliderect(solid) for solid in solids)
