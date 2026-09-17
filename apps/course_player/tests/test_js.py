"""Runs the course player's JavaScript unit tests with node, when node is installed."""

import shutil
import subprocess
import unittest
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

NODE = shutil.which("node")
TEST_FILE = Path(__file__).resolve().parent / "js" / "course_player.test.js"


@unittest.skipUnless(NODE, "node is not installed")
class CoursePlayerJavaScriptTests(SimpleTestCase):
    def test_pure_helpers(self) -> None:
        result = subprocess.run(
            [NODE, str(TEST_FILE), str(settings.BASE_DIR)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("passed", result.stdout)
