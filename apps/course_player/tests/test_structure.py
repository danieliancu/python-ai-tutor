"""The real player keeps the existing product shell's structure (no redesign)."""

import re
from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase

from apps.course_player.tests.helpers import PlayerFixtures

LANDMARKS = (
    'class="app"',
    'class="topbar"',
    'class="primary-nav"',
    'class="stats-bar"',
    'class="shell"',
    'id="lesson" class="lesson"',
    'class="breadcrumb"',
    'class="pager"',
    'class="lesson__head"',
    'class="exercise"',
    'class="editor"',
    'class="editor__tabs"',
    'class="run-row"',
    'class="btn-run"',
    'class="console"',
    'class="console__output"',
    'id="progress" class="side-progress"',
    'class="ring"',
    'id="skill-map" class="skill-map"',
    'class="quote"',
    'id="tutor" class="side-tutor"',
    'class="tutor__thread"',
    'class="tutor__feedback"',
    'class="ask"',
    'id="next-up" class="next-up"',
    'class="btn-outline"',
    'class="tagline"',
    'class="site-footer"',
)
FRAMEWORKS = ("react", "vue", "tailwind", "bootstrap", "cdn.", "unpkg", "jsdelivr")


class ShellStructureTests(PlayerFixtures, TestCase):
    def test_real_and_demo_pages_share_the_layout(self) -> None:
        real = self.open(self.code).content.decode()
        demo = Client().get("/").content.decode()
        for landmark in LANDMARKS:
            with self.subTest(landmark=landmark):
                self.assertIn(landmark, real)
                self.assertIn(landmark, demo)

    def test_scripts_are_local_and_not_inline(self) -> None:
        html = self.open(self.code).content.decode()
        scripts = re.findall(r"<script([^>]*)>(.*?)</script>", html, re.S)
        inline = [
            attrs
            for attrs, body in scripts
            if body.strip()
            and 'type="application/json"' not in attrs
            # base.html's one-line no-js → js class switch is part of the shell
            and "classList.replace" not in body
        ]
        self.assertEqual(inline, [])
        self.assertIn('src="/static/js/course_player.js"', html)
        for framework in FRAMEWORKS:
            self.assertNotIn(framework, html.lower())

    def test_css_is_only_extended(self) -> None:
        css = (Path(settings.BASE_DIR) / "static" / "css" / "base.css").read_text(encoding="utf-8")
        self.assertIn("/* --- Course player controls", css)
        for rule in (".editor__code {", ".btn-run {", ".bubble {", '.skill[data-state="learning"]'):
            self.assertIn(rule, css)

    def test_no_unsafe_html_insertion_in_js(self) -> None:
        js = (Path(settings.BASE_DIR) / "static" / "js" / "course_player.js").read_text(
            encoding="utf-8"
        )
        # The only innerHTML use parses the server-rendered progress fragment.
        self.assertEqual(js.count("innerHTML"), 1)
        self.assertIn("fragment.innerHTML = result.body", js)
        self.assertNotIn("eval(", js)
        self.assertNotIn("alert(", js)
        self.assertIn("textContent", js)
