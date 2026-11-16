"""Saving and loading progress to saves/save.json."""
import json, os, sys
from datetime import datetime
from settings import Config
from level import checkpoint_positions

# The powers a Lucky Block can give (None = no power).
valid_powers = (None, "fly", "crush", "jump")


def report_problem(message):
    # Printed instead of hidden, so you can always see WHY a save was ignored.
    print(f"[save] {message}", file=sys.stderr)


def ensure_save(): os.makedirs(Config.save_directory, exist_ok=True)


def save_game(level, lives, checkpoint=None, power=None, power_timer=0):
    """Write progress to disk. Returns True on success, False if the file could not be written."""
    data = {"level": level, "lives": lives, "checkpoint": checkpoint,
            "power": power, "power_timer": power_timer,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
    temp_path = Config.save_file_path + ".tmp"
    try:
        ensure_save()
        # Write to a temp file first and swap it in afterwards, so a crash in the middle of
        # writing can never leave a half-written (corrupt) save behind.
        with open(temp_path, "w", encoding="utf-8") as save_file:
            json.dump(data, save_file)
        os.replace(temp_path, Config.save_file_path)
        # Do not trust the write: read the file back and compare. "True" must mean it is really on disk.
        with open(Config.save_file_path, encoding="utf-8") as written_file:
            if json.load(written_file) != data:
                raise OSError("the file on disk is not what was written")
        return True
    except (OSError, ValueError, TypeError) as error:   # disk full, no permission, read-only folder, bad read-back...
        report_problem(f"could not write save file: {error}")
        return False


def clear_save():
    """Delete the save file, so nothing can be continued. Returns True if it is gone."""
    try:
        os.remove(Config.save_file_path)
    except (FileNotFoundError, NotADirectoryError):
        pass                                          # already gone (or its folder does not even exist): what we wanted
    except OSError as error:
        report_problem(f"could not delete save file: {error}")
        return False
    return True


def is_whole_number(value):
    # In Python True/False count as ints, but they are not a valid level or number of lives.
    return isinstance(value, int) and not isinstance(value, bool)


def validate_save_data(data):
    """Return a clean copy of the save data, or raise ValueError that says what is wrong."""
    if not isinstance(data, dict):
        raise ValueError("save data is not a JSON object")

    level = data.get("level")
    if not is_whole_number(level) or not 1 <= level <= Config.max_levels:
        raise ValueError(f"level must be a whole number from 1 to {Config.max_levels}, got {level!r}")

    lives = data.get("lives")
    if not is_whole_number(lives) or not 1 <= lives <= Config.starting_lives:
        raise ValueError(f"lives must be a whole number from 1 to {Config.starting_lives}, got {lives!r}")

    checkpoint = data.get("checkpoint")
    if checkpoint is not None:
        # Being "somewhere inside the level" is not enough: the position must be the exact spot of
        # one of THIS level's checkpoints (a made-up 4600 once sent Continue into the next level).
        if not is_whole_number(checkpoint):
            raise ValueError(f"checkpoint must be empty or a whole number, got {checkpoint!r}")
        valid_spots = checkpoint_positions(level)
        if checkpoint not in valid_spots:
            raise ValueError(f"checkpoint {checkpoint!r} is not a checkpoint of level {level} (they are at {list(valid_spots)})")

    power = data.get("power")            # saves made before powers were stored simply have none
    if power not in valid_powers:
        raise ValueError(f"unknown power {power!r}")

    power_timer = data.get("power_timer", 0)
    if not is_whole_number(power_timer) or not 0 <= power_timer <= Config.power_duration_frames:
        raise ValueError(f"power_timer must be a whole number from 0 to {Config.power_duration_frames}, got {power_timer!r}")
    if power is None or power_timer == 0:
        power, power_timer = None, 0     # an expired power is no power

    return {"level": level, "lives": lives, "checkpoint": checkpoint,
            "power": power, "power_timer": power_timer}


def load_game():
    """Return the saved progress as a validated dict, or None if there is no usable save."""
    try:
        with open(Config.save_file_path, encoding="utf-8") as save_file:
            return validate_save_data(json.load(save_file))
    except FileNotFoundError:
        return None                                   # first run: no save yet, that's normal
    except OSError as error:                          # unreadable file, a folder in its place, no permission...
        report_problem(f"cannot read save file: {error}")
    except ValueError as error:                       # broken JSON, bad bytes, or values that make no sense
        report_problem(f"ignoring damaged save file: {error}")
    return None


def has_save():
    """True only when the save file exists AND is healthy enough to continue from."""
    return load_game() is not None
