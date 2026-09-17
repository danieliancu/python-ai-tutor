import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from apps.python_runner.docker_backend import DockerBackend
from apps.python_runner.fixtures import (
    MAX_FIXTURE_BYTES,
    MAX_FIXTURE_FILES,
    FixtureRejected,
    validate_fixture_files,
)
from apps.python_runner.runner import PythonRunner, bootstrap_source, harness_source
from apps.python_runner.tests.fakes import ENABLED, FakeBackend, harness_reply, outcome

SECRET_ROWS = "date,amount\n2026-01-01,SECRET-ROW-42\n"


class FixturePolicyTests(SimpleTestCase):
    def test_plain_file_names_are_allowed(self) -> None:
        for name in ("data.csv", "transactions.csv", "inventory.json", "notes", "a_b-c.v2.txt"):
            with self.subTest(name=name):
                self.assertEqual(validate_fixture_files({name: "x"}), {name: "x"})

    def test_paths_and_odd_names_are_rejected(self) -> None:
        for name in (
            "../data.csv",
            "../../secret",
            "/absolute.txt",
            "C:\\secret.txt",
            "C:secret.txt",
            "subdir/../../secret",
            "sub/data.csv",
            "..",
            ".hidden",
            "data..csv",
            "data.csv.",
            "",
            "a" * 65,
            "learner.py",
            "HARNESS.py",
            "bootstrap.py",
            "data csv",
            "données.csv",
            7,
        ):
            with self.subTest(name=name), self.assertRaises(FixtureRejected):
                validate_fixture_files({name: "x"})

    def test_content_and_size_limits(self) -> None:
        with self.assertRaises(FixtureRejected):
            validate_fixture_files({"a.txt": b"bytes"})
        with self.assertRaises(FixtureRejected):
            validate_fixture_files({"a.txt": "nul\x00"})
        with self.assertRaises(FixtureRejected):
            validate_fixture_files({"a.txt": "\ud800"})
        with self.assertRaises(FixtureRejected):
            validate_fixture_files({"a.txt": "x" * (MAX_FIXTURE_BYTES + 1)})
        validate_fixture_files({"a.txt": "x" * MAX_FIXTURE_BYTES})
        many = {f"f{i}.txt": "x" for i in range(MAX_FIXTURE_FILES + 1)}
        with self.assertRaises(FixtureRejected):
            validate_fixture_files(many)
        with self.assertRaises(FixtureRejected):
            validate_fixture_files(["a.txt"])


class RunnerFixtureTests(SimpleTestCase):
    def test_without_fixtures_nothing_changes(self) -> None:
        backend = FakeBackend(lambda *args: outcome(stdout="hi\n"))
        runner = PythonRunner(ENABLED, backend)
        runner.run_program("print('hi')", "")
        runner.run_program("print('hi')", "", extra_files={})
        for request in backend.requests:
            self.assertEqual(request["files"], {"learner.py": "print('hi')"})
            self.assertEqual(request["argv"], ["/sandbox/learner.py"])

    def test_program_with_fixtures_runs_through_the_bootstrap(self) -> None:
        backend = FakeBackend(lambda *args: outcome(stdout="1\n"))
        result = PythonRunner(ENABLED, backend).run_program(
            "print(len(open('data.csv').readlines()))", extra_files={"data.csv": SECRET_ROWS}
        )
        request = backend.requests[0]
        self.assertEqual(
            request["files"],
            {
                "learner.py": "print(len(open('data.csv').readlines()))",
                "bootstrap.py": bootstrap_source(),
                "fixtures/data.csv": SECRET_ROWS,
            },
        )
        self.assertEqual(request["argv"], ["/sandbox/bootstrap.py", "/sandbox/learner.py"])
        self.assertEqual(result.stdout, "1\n")

    def test_functions_with_fixtures(self) -> None:
        backend = FakeBackend(
            lambda files, argv, stdin: harness_reply(stdin, [{"ok": True, "value": 2}])
        )
        results = PythonRunner(ENABLED, backend).run_functions(
            "def count(): ...", "count", [([], {})], extra_files={"data.csv": SECRET_ROWS}
        )
        request = backend.requests[0]
        self.assertEqual(request["argv"], ["/sandbox/bootstrap.py", "/sandbox/harness.py"])
        self.assertEqual(request["files"]["harness.py"], harness_source())
        self.assertEqual(request["files"]["fixtures/data.csv"], SECRET_ROWS)
        # The harness request carries only the call, never fixture content.
        self.assertNotIn("SECRET-ROW", request["stdin"])
        self.assertEqual(json.loads(request["stdin"])["function_name"], "count")
        self.assertEqual(results[0].value, 2)

    def test_unsafe_fixtures_never_reach_the_backend(self) -> None:
        backend = FakeBackend(lambda *args: outcome())
        with self.assertRaises(FixtureRejected):
            PythonRunner(ENABLED, backend).run_program("print(1)", extra_files={"../x": "y"})
        self.assertEqual(backend.requests, [])

    def test_bootstrap_copies_fixtures_then_runs_the_target(self) -> None:
        source = bootstrap_source()
        self.assertIn('FIXTURE_DIR = "/sandbox/fixtures"', source)
        self.assertIn('runpy.run_path(target, run_name="__main__")', source)


class BackendFileLayoutTests(SimpleTestCase):
    def test_fixture_directory_is_created_inside_the_mount(self) -> None:
        with TemporaryDirectory() as directory:
            DockerBackend._write_files(
                Path(directory),
                {"learner.py": "print(1)", "fixtures/data.csv": SECRET_ROWS},
            )
            root = Path(directory)
            self.assertEqual((root / "learner.py").read_text(encoding="utf-8"), "print(1)")
            self.assertEqual(
                (root / "fixtures" / "data.csv").read_text(encoding="utf-8"), SECRET_ROWS
            )

    def test_paths_outside_the_mount_are_refused(self) -> None:
        for name in ("../escape.txt", "fixtures/../../escape.txt", "a/b/c.txt"):
            with (
                self.subTest(name=name),
                TemporaryDirectory() as directory,
                self.assertRaises(ValueError),
            ):
                DockerBackend._write_files(Path(directory), {name: "x"})
