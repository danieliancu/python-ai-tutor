"""All level maths. Levels are derived from total XP and never stored.

Reaching level N takes 100 * N * (N - 1) / 2 XP in total: level 1 at 0 XP, level 2 at 100,
level 3 at 300, level 4 at 600, level 5 at 1000.
"""

from math import isqrt

XP_STEP = 100


def xp_floor_for_level(level: int) -> int:
    """Total XP needed to reach ``level`` (level 1 needs none)."""
    level = max(level, 1)
    return XP_STEP * level * (level - 1) // 2


def xp_required_for_next_level(level: int) -> int:
    """Total XP needed to reach the level after ``level``."""
    return xp_floor_for_level(max(level, 1) + 1)


def level_for_xp(total_xp: int) -> int:
    """The highest level whose threshold ``total_xp`` has reached."""
    xp = max(int(total_xp), 0)
    # Solve 100 * n * (n - 1) / 2 <= xp, then correct any rounding at the boundary.
    level = max((1 + isqrt(1 + 8 * xp // XP_STEP)) // 2, 1)
    while xp_floor_for_level(level + 1) <= xp:
        level += 1
    while level > 1 and xp_floor_for_level(level) > xp:
        level -= 1
    return level


def level_progress(total_xp: int) -> dict:
    """Level, the current and next thresholds, and whole-percent progress between them."""
    xp = max(int(total_xp), 0)
    level = level_for_xp(xp)
    floor = xp_floor_for_level(level)
    next_floor = xp_required_for_next_level(level)
    return {
        "level": level,
        "xp": xp,
        "floor": floor,
        "next": next_floor,
        "percent": 100 * (xp - floor) // (next_floor - floor),
    }
