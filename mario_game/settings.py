"""Game constants (Config), colors and the story chapters."""
import os


class Config:
    # --- Screen / world ---
    screen_width, screen_height       = 800, 600
    level_width           = 4800
    frames_per_second          = 60
    max_levels   = 50

    # --- Gravity ---
    gravity         = 0.75
    fall_gravity_multiplier    = 1.60
    max_fall_speed     = 18
    ground_y     = 550

    # --- Player movement ---
    player_speed      = 5
    dash_speed   = 11
    player_jump_speed       = -15.5
    player_double_jump_speed      = -13.0
    jump_hold_frames    = 14
    dash_duration     = 14
    dash_cooldown      = 45
    double_tap_window   = 12
    punch_duration    = 18
    invincibility_duration      = 90

    # --- Enemies ---
    enemy_speed  = 3
    enemy_gravity   = 0.6
    enemy_patrol_range = 120
    enemy_body_gap = 10
    enemy_spawn_distance_from_player = 600

    # --- AI companions (Luigi / Princess / Yoshi) ---
    companion_speed   = 4.5
    companion_gravity    = 0.75
    companion_jump_speed    = -13.0
    companion_near_distance    = 50
    companion_far_distance     = 130
    companion_jump_speed_2     = -11.0   # 2nd jump of a team member climbing over a pipe (from its rim)
    companion_jump_speed_3     = -9.0    # 3rd jump
    companion_wall_look_ahead  = 22      # how far ahead a team member looks for a wall before it starts a jump
    companion_clear_rise       = 26      # it must rise this much before it moves forward over an obstacle
    companion_edge_look_ahead = 22

    # --- Level generation spacing ---
    tile_size         = 32
    min_pipe_gap = 220
    max_platform_gap = 150      # neighbouring platforms never leave a wider gap than this (a normal jump crosses ~171)
    max_platform_hop = 286      # ...unless they are further apart than even a double jump can cross
    min_enemy_gap= 180
    enemy_pipe_clearance = 70          # enemies starting closer than this to a pipe are removed
    checkpoint_pipe_margin = 200       # a checkpoint (and the team behind it) stays this far from pipes

    # Pipes always stand in these exact spots (x of the pipe's left side), the same in every level.
    # The first chapter uses the first 3; each later chapter adds one more.
    pipe_layout  = (900, 1500, 2100, 2360, 3000, 3500, 3760)
    pipes_in_first_chapter = 3

    # --- Rules ---
    starting_lives = 3
    player_start_x = 50                # where a fresh level starts Mario
    power_duration_frames = 180        # how long a lucky-block power lasts (3 seconds at 60 fps)
    # True: standing on the middle of a pipe top kills Mario (the edge overhang is always safe).
    # False: pipes are ordinary solid obstacles you can stand on without any danger.
    pipe_top_kills = False
    pipe_sink_frames = 40              # length of the "sinking into the pipe" death animation
    fall_death_margin = 80             # Mario dies this many pixels below the bottom of the screen

    # --- Player body and jumping (see Mario.press_jump / Mario._apply_jump_and_gravity) ---
    player_width, player_height = 32, 38
    power_jump_speed = -22             # first jump while the "jump" power is active
    power_double_jump_speed = -19      # second jump while the "jump" power is active
    fly_speed = 4.5                    # "fly" power: Mario rises at this speed while UP / SPACE / W is held, sinks while DOWN / S is held,
                                       # and hovers otherwise (gravity is switched off). Same as the HTML game.
    boss_hit_limit = 10                # in a boss fight Mario can take this many hits before he loses a life (HTML game: 10 hearts)
    boss_hit_invincibility = 60        # frames of protection after each hit
    jump_release_damping = 0.82        # upward speed is multiplied by this when jump is released early
    squash_on_jump = -0.8              # sprite stretch / squash amounts (purely visual)
    squash_on_landing = 0.6
    squash_decay = 0.72

    # --- Combat ---
    enemy_squish_frames = 20           # how long a squashed enemy stays on screen
    crush_power_range = 90             # horizontal reach of the "crush" power (centre to centre)
    crush_power_range_y = 60           # vertical reach: an enemy further above / below than this is NOT hit
    boss_arena_width = 900             # the boss fight happens in the last 900px of the level; the boss never leaves it
    punch_enemy_size = (34, 24)        # punch hit box against normal enemies (width, height)
    punch_boss_size = (44, 26)         # punch hit box against the boss
    punch_y_offset = 8                 # the punch starts this far below the top of Mario
    stomp_tolerance_enemy = 8          # how far below an enemy's top a landing still counts as a stomp
    stomp_tolerance_boss = 10
    stomp_bounce_enemy = -10           # upward speed after stomping an enemy
    stomp_bounce_boss = -14            # ...and after stomping the boss
    boss_shell_size = 16               # hit box of a boss projectile
    block_bump_speed = 2               # downward speed after bumping a lucky block with the head
    block_touch_margin = 1             # solid blocks only touch Mario's edge, so look this far around him

    # --- Team / respawn ---
    companion_start_offsets = (55, 100, 145)   # Luigi, Princess, Yoshi: distance behind Mario at level start
    companion_respawn_spacing = 55             # distance between team members after a respawn

    # --- Messages and screen effects (frames) ---
    flash_frames_life = 70
    flash_frames_power = 70
    flash_frames_checkpoint = 80
    flash_frames_boss_hit = 45
    shake_block, shake_stomp, shake_punch = 4, 3, 3
    shake_boss_hit, shake_boss_defeated = 5, 8

    # --- Screens and timing (frames) ---
    falling_text_y = 240
    falling_text_delay = 5
    falling_text_hold_frames = 60      # pause after the letters stop falling
    credits_hold_frames = 120
    cutscene_frames = 300
    ending_walk_frames = 180           # Mario walks to the princess
    ending_hearts_frames = 260         # "happily ever after" scene
    heart_beat_speed = 0.055
    max_catch_up_steps = 60            # most logic steps run in one drawn frame (= 1 second); a longer freeze is dropped, not caught up

    # --- Saving ---
    save_directory     = "saves"
    save_file_path    = os.path.join("saves", "save.json")


black   = (  0,   0,   0)
white   = (255, 255, 255)
sky     = (104, 184, 232)
sky_dark    = ( 40,  80, 140)
red     = (220,  30,  30)
dark_red   = (120,   0,   0)
yellow  = (255, 210,   0)
green   = (  0, 180,   0)
dark_green = (  0,  90,   0)
light_green = (160, 255, 100)
brown   = (139,  69,  19)
dark_brown = ( 80,  40,   5)
orange  = (255, 130,   0)
gray    = (140, 140, 140)
light_gray  = (210, 210, 210)
skin    = (255, 210, 155)
pink    = (255, 182, 193)
light_pink   = (255, 220, 230)
pipe_green   = ( 30, 160,  40)
pipe_dark_green  = (  0,  80,  10)
gold    = (255, 200,  30)
cyan    = (  0, 220, 220)


chapters = [
    ("Mushroom Kingdom", "Mario begins his quest through the bright Mushroom Kingdom. Bowser awaits!"),
    ("Princess Castle", "After Bowser flees, Luigi joins the team. The princess is held in a castle prison."),
    ("Deep Space", "Bowser's child attacks from space! Yoshi the dino joins the team."),
    ("Lava Castle", "Bowser attacks from his lava fortress. He falls... but returns as a skeleton!"),
    ("Shadow Realm", "Skeleton Bowser's last stand. Mario and team must end this forever!"),
]


def chapter_for_level(level):
    return min(4, max(0, (level-1)//10))