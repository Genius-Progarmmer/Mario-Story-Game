"""Level generation: background, platforms, pipes, enemies, checkpoints and the boss."""
import random
from functools import lru_cache
import pygame
from settings import Config, chapter_for_level
from world_objects import LuckyBlock, Pipe, Checkpoint
from enemies import Mushroom, Turtle


def make_bg_surface(chapter=0):
    surface = pygame.Surface((Config.level_width, Config.screen_height))
    themes = [
        ((104,184,232),(40,80,140)),
        ((72,24,130),(16,8,60)),
        ((10,16,55),(2,2,20)),
        ((160,40,12),(60,8,0)),
        ((28,8,55),(5,0,20)),
    ]
    sky_top, sky_bottom = themes[min(4, chapter)]
    for y in range(Config.screen_height):
        blend = y/Config.screen_height
        red_channel = int(sky_top[0]*(1-blend)+sky_bottom[0]*blend)
        green_channel = int(sky_top[1]*(1-blend)+sky_bottom[1]*blend)
        blue_channel = int(sky_top[2]*(1-blend)+sky_bottom[2]*blend)
        pygame.draw.line(surface,(red_channel,green_channel,blue_channel),(0,y),(Config.level_width,y))
    if chapter == 0:
        pygame.draw.circle(surface,(255,240,100),(Config.level_width-130,80),38)
        pygame.draw.circle(surface,(255,255,190),(Config.level_width-130,80),28)
    cloud_random_generator = random.Random(999)
    for _ in range(26 if chapter < 2 else 45):
        cloud_x=cloud_random_generator.randint(0,Config.level_width-160); cloud_y=cloud_random_generator.randint(40,210); cloud_width=cloud_random_generator.randint(70,150); cloud_height=cloud_width//3
        cloud_color=(245,245,255) if chapter<2 else ((100,40,120) if chapter==4 else (100,35,20))
        pygame.draw.ellipse(surface,cloud_color,(cloud_x,cloud_y,cloud_width,cloud_height))
        pygame.draw.ellipse(surface,cloud_color,(cloud_x+cloud_width//4,cloud_y-cloud_height//2,cloud_width//2,cloud_height))
        pygame.draw.ellipse(surface,cloud_color,(cloud_x+cloud_width//8,cloud_y-cloud_height//4,cloud_width*3//4,cloud_height))
    hill_random_generator = random.Random(777)
    for _ in range(18):
        hill_x=hill_random_generator.randint(0,Config.level_width-300); hill_width=hill_random_generator.randint(160,320); hill_height=hill_random_generator.randint(60,150)
        hill_color=(80,160,60) if chapter==0 else ((80,20,80) if chapter==4 else (90,50,40))
        hill_highlight_color=(100,180,70) if chapter==0 else ((110,35,110) if chapter==4 else (120,65,45))
        pygame.draw.ellipse(surface,hill_color,(hill_x,Config.ground_y-hill_height,hill_width,hill_height*2))
        pygame.draw.ellipse(surface,hill_highlight_color,(hill_x+22,Config.ground_y-hill_height+12,hill_width-44,hill_height*2-24))
    return surface


def _inside_any(rect, obstacles):
    """Does this rectangle overlap any obstacle?"""
    return rect.collidelist(obstacles) != -1


def _nudge_to_free_spot(enemy, platforms, obstacles):
    """Move an enemy sideways along the platform it stands on until it overlaps nothing.

    Returns True when a free spot was found (the enemy is moved there), False otherwise.
    """
    floor = enemy.rect.move(0, 4).collidelist(platforms[1:])      # floating platforms only
    if floor == -1: return False
    platform = platforms[1:][floor]
    for candidate_x in range(platform.left + 2, platform.right - enemy.rect.w - 1, 4):
        trial = enemy.rect.copy(); trial.x = candidate_x
        if not _inside_any(trial, obstacles):
            enemy.rect.x = enemy.start_x = candidate_x
            return True
    return False


def level_random(level_number):
    """The random generator of a level: seeded by the level number, so everything that is built
    with it (platforms, pipes, blocks AND the rewards inside the blocks) is the same every time."""
    return random.Random(level_number * 0xDEAD_BEEF)


@lru_cache(maxsize=None)
def checkpoint_positions(level_number):
    """The x positions of every checkpoint of a level (used to check a save file)."""
    built = build_level(level_number, level_random(level_number))
    return tuple(sorted(checkpoint.world_x for checkpoint in built[3]))


def build_level(level_number, random_generator, player_x=50):
    platforms=[]; enemies=[]; pipes=[]; checkpoints=[]; lucky_blocks=[]; boss=None
    is_boss=(level_number%10==0); final=(level_number==50)
    ground_y = Config.ground_y
    platforms.append(pygame.Rect(0, ground_y, Config.level_width, 50))

    def is_near_pipe(x, margin):
        return any(pipe.world_x - margin < x < pipe.world_x + Pipe.width + margin for pipe in pipes)

    def move_clear_of_pipes(x, margin):
        # Slide right until x is no longer close to any pipe.
        while is_near_pipe(x, margin): x += 20
        return x

    def in_boss_arena(left, right):
        # A boss level keeps its fight zone (the last Config.boss_arena_width px) free of platforms, blocks and
        # enemies: otherwise Mario can hop on a platform high above the boss, where it cannot reach him.
        return is_boss and right > Config.level_width - Config.boss_arena_width

    def add_floating_platform(x, y, width=110):
        if in_boss_arena(x, x + width): return False
        # A platform right above a pipe would block the jump over it, so skip those.
        # Returns True if the platform was added, so anything sitting on it can be skipped too.
        if any(x < pipe.world_x + Pipe.width + 40 and x + width > pipe.world_x - 40 for pipe in pipes):
            return False
        platforms.append(pygame.Rect(x,y,width,Config.tile_size//2))
        return True

    def enemy_spawn_clear(x):
        if abs(x - player_x) < Config.enemy_spawn_distance_from_player:
            return False
        return all(abs(enemy.rect.x - x) >= Config.min_enemy_gap for enemy in enemies)

    def add_enemy(x):
        if in_boss_arena(x, x + 34) or not enemy_spawn_clear(x): return
        enemies.append(Mushroom(x, ground_y-30, 120))

    def add_enemy_on_platform(x, y):
        if in_boss_arena(x, x + 34) or not enemy_spawn_clear(x): return
        enemies.append(Mushroom(x, y-30, 80))

    def add_pipe(x):
        # Only place a pipe where there is solid ground under it.
        has_ground = any(platform.h>=50 and platform.x<=x and platform.x+platform.w>=x+Pipe.width for platform in platforms)
        if not has_ground: return
        for existing_pipe in pipes:
            if abs(existing_pipe.world_x - x) < Config.min_pipe_gap: return
        pipes.append(Pipe(x, ground_y))

    def add_checkpoint(x):
        # Never put a checkpoint near a pipe: Mario respawns there and his companions stand up to
        # ~165px behind him, so the margin must be wider than that or they would spawn inside the pipe.
        checkpoints.append(Checkpoint(move_clear_of_pipes(x, Config.checkpoint_pipe_margin), ground_y))

    def add_lucky_block(x, y, reward=None):
        # Low blocks would sit inside a pipe's space, so slide them clear of any pipe.
        if y > ground_y - 150: x = move_clear_of_pipes(x, 60)
        if in_boss_arena(x, x + Config.tile_size): return
        # The reward comes from the level's own generator (not from the global `random`), so the
        # same level always hides the same powers in the same blocks.
        if reward is None: reward = random_generator.choice(("fly", "crush", "jump"))
        new_block = LuckyBlock(x, y, reward)
        if any(new_block.rect.colliderect(other.rect) for other in lucky_blocks): return
        lucky_blocks.append(new_block)

    x=400; checkpoint_placed=False

    # Pipes are NOT random: they always stand in the same spots (see Config.pipe_layout).
    # Later chapters use more of the layout, so the level gets harder as the story goes on.
    pipe_count = Config.pipes_in_first_chapter + chapter_for_level(level_number)
    for pipe_x in Config.pipe_layout[:pipe_count]:
        add_pipe(pipe_x)

    # Every level gets one guaranteed Lucky Block near the middle; its reward cycles by level number.
    add_lucky_block(Config.level_width//2 + random_generator.randint(-200, 200), ground_y-100,
       ("fly", "crush", "jump")[(level_number-1) % 3])

    while x < Config.level_width - 600:
        section_type = random_generator.randint(0,3)

        if section_type == 0:
            section_length = random_generator.randint(250,420)
            add_enemy(x + random_generator.randint(60, max(61,section_length-80)))
            if random_generator.random()<0.5:
                add_lucky_block(x + random_generator.randint(60,max(61,section_length-60)), ground_y-80)
            x += section_length

        elif section_type == 1:
            section_length=random_generator.randint(350,550); platform_count=random_generator.randint(2,3)
            platform_width=random_generator.randint(90,140); spacing=section_length//platform_count
            for index in range(platform_count):
                platform_x=x+index*spacing+random_generator.randint(10,30); height_above_ground=random_generator.randint(110,210)
                if not add_floating_platform(platform_x, ground_y-height_above_ground, platform_width):
                    continue
                if random_generator.random()<0.4: add_enemy_on_platform(platform_x+10, ground_y-height_above_ground)
                if random_generator.random()<0.35: add_lucky_block(platform_x+platform_width//2-Config.tile_size//2, ground_y-height_above_ground-Config.tile_size-4)
            if random_generator.random()<0.4: add_enemy(x+random_generator.randint(20,70))
            x += section_length

        elif section_type == 2:
            section_length=random_generator.randint(380,520)
            if random_generator.random()<0.5: add_enemy(x+random_generator.randint(20,80))
            x += section_length

        else:
            section_length=random_generator.randint(380,520)
            height_above_ground=random_generator.randint(120,200)
            if add_floating_platform(x+section_length//2, ground_y-height_above_ground, 100):
                add_lucky_block(x+section_length//2+36, ground_y-height_above_ground-Config.tile_size-4)
            add_enemy(x+random_generator.randint(200, min(300,section_length-60)))
            x += section_length

        if not checkpoint_placed and x > Config.level_width//2:
            add_checkpoint(x-100); checkpoint_placed=True

    # Platforms that are close enough to hop between must be spaced for a normal jump: grow one of the
    # two towards the other. Not where that would cover a pipe, a Lucky Block or another platform.
    def room_for(rect):
        if any(rect.left < pipe.world_x + Pipe.width + 40 and rect.right > pipe.world_x - 40 for pipe in pipes): return False
        if any(rect.colliderect(block.rect) for block in lucky_blocks): return False
        return not any(rect.colliderect(other) for other in platforms[1:])
    ordered = sorted(platforms[1:], key=lambda platform: platform.x)
    for left, right in zip(ordered, ordered[1:]):
        gap = right.left - left.right
        if not (Config.max_platform_gap < gap <= Config.max_platform_hop): continue
        grow = gap - Config.max_platform_gap
        grown_left = pygame.Rect(left.right, left.y, grow, left.h)
        grown_right = pygame.Rect(right.left - grow, right.y, grow, right.h)
        if room_for(grown_left): left.w += grow
        elif room_for(grown_right): right.x -= grow; right.w += grow

    # Last safety pass: no enemy may start inside a wall, a pipe or a Lucky Block (they would be stuck).
    # An enemy on a narrow platform is first moved to a free spot on the same platform; if there is
    # none (or it is too close to a pipe) it is simply dropped.
    pipe_xs = [placed_pipe.world_x for placed_pipe in pipes]
    obstacles = platforms + [pipe.shaft for pipe in pipes] + [pipe.lip_center for pipe in pipes]
    obstacles += [block.rect for block in lucky_blocks]
    enemies[:] = [enemy for enemy in enemies
                  if not any(abs(enemy.rect.x - pipe_x) < Config.enemy_pipe_clearance for pipe_x in pipe_xs)]
    kept_enemies = []
    for enemy in enemies:
        if not _inside_any(enemy.rect, obstacles) or _nudge_to_free_spot(enemy, platforms, obstacles):
            kept_enemies.append(enemy)
    enemies[:] = kept_enemies

    goal_x = Config.level_width - 200
    goal = pygame.Rect(goal_x, ground_y-48, 40, 48)
    if is_boss:
        chapter = chapter_for_level(level_number)
        variants = ("normal", "normal", "space", "lava", "undead")
        boss = Turtle(goal_x-300, ground_y-80, health=6+level_number//8, final=final,
                      variant=variants[chapter])
    if not checkpoint_placed: add_checkpoint(Config.level_width//2)
    add_checkpoint(goal_x-400)
    return platforms, enemies, pipes, checkpoints, lucky_blocks, boss, goal


def collect_solids(level):
    """Return every rectangle that should block a character.

    The level keeps its existing grouped objects for rendering and gameplay,
    while this single list gives all characters one authoritative collision
    surface.  Pipes contribute their shaft and the centre of their lip (the overhanging
    edges are not solid); Lucky Blocks contribute their block rectangle.
    """
    platforms, _enemies, pipes, _checkpoints, lucky_blocks, _boss, _goal = level
    solids = list(platforms)
    for pipe in pipes:
        solids.extend((pipe.shaft, pipe.lip_center))
    # (Lucky Blocks are NOT solid: they are items Mario can walk or jump into, see Game._update_lucky_blocks)
    return solids


def enemy_body_solids(enemies, current):
    """Create temporary collision rectangles for the other live enemies.

    The extra horizontal padding preserves a visible gap instead of allowing
    two 32px enemy sprites to touch.  These are temporary copies, so enemy
    rectangles themselves remain the source of truth.
    """
    gap = Config.enemy_body_gap
    blockers = []
    for other in enemies:
        if other is current or not other.alive or other.squish > 0:
            continue
        blockers.append(other.rect.inflate(gap * 2, 0))
    return blockers