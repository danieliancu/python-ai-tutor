from django.test import SimpleTestCase

from apps.gamification.levels import (
    level_for_xp,
    level_progress,
    xp_floor_for_level,
    xp_required_for_next_level,
)


class LevelTests(SimpleTestCase):
    def test_thresholds(self) -> None:
        self.assertEqual(
            [xp_floor_for_level(n) for n in range(1, 7)], [0, 100, 300, 600, 1000, 1500]
        )
        self.assertEqual(xp_required_for_next_level(1), 100)
        self.assertEqual(xp_required_for_next_level(4), 1000)

    def test_boundaries(self) -> None:
        cases = {
            0: (1, 0, 100, 0),
            1: (1, 0, 100, 1),
            99: (1, 0, 100, 99),
            100: (2, 100, 300, 0),
            101: (2, 100, 300, 0),
            299: (2, 100, 300, 99),
            300: (3, 300, 600, 0),
            450: (3, 300, 600, 50),
            599: (3, 300, 600, 99),
            600: (4, 600, 1000, 0),
            999: (4, 600, 1000, 99),
            1000: (5, 1000, 1500, 0),
            4950: (10, 4500, 5500, 45),
        }
        for xp, (level, floor, next_floor, percent) in cases.items():
            with self.subTest(xp=xp):
                self.assertEqual(level_for_xp(xp), level)
                self.assertEqual(
                    level_progress(xp),
                    {
                        "level": level,
                        "xp": xp,
                        "floor": floor,
                        "next": next_floor,
                        "percent": percent,
                    },
                )

    def test_every_level_boundary_is_exact(self) -> None:
        for level in range(1, 200):
            floor = xp_floor_for_level(level)
            self.assertEqual(level_for_xp(floor), level)
            if floor:
                self.assertEqual(level_for_xp(floor - 1), level - 1)

    def test_negative_xp_is_level_one(self) -> None:
        self.assertEqual(level_for_xp(-50), 1)
        self.assertEqual(level_progress(-50)["xp"], 0)
