from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from apps.python_runner.config import RunnerConfig, get_runner_config
from apps.python_runner.results import FunctionCallResult, PythonRunResult, RunStatus


class RunnerConfigTests(SimpleTestCase):
    def test_safe_defaults(self) -> None:
        config = RunnerConfig.from_settings({})
        self.assertEqual(config.backend, "disabled")
        self.assertFalse(config.enabled)
        self.assertEqual(config.image, "python:3.11-slim")
        self.assertEqual(config.timeout_seconds, 3.0)
        self.assertEqual(config.memory_mb, 128)
        self.assertEqual(config.cpus, 0.5)
        self.assertEqual(config.pids_limit, 64)
        self.assertEqual(config.max_output_bytes, 65536)
        self.assertEqual(config.max_source_bytes, 65536)
        self.assertEqual(config.docker_binary, "docker")

    def test_normal_test_suite_never_enables_docker(self) -> None:
        self.assertEqual(settings.PYTHON_RUNNER["BACKEND"], "disabled")
        self.assertFalse(get_runner_config().enabled)

    def test_docker_backend_and_overrides(self) -> None:
        config = RunnerConfig.from_settings(
            {
                "BACKEND": " Docker ",
                "IMAGE": "python@sha256:abc",
                "TIMEOUT_SECONDS": "2.5",
                "MEMORY_MB": "256",
                "CPUS": "1",
                "PIDS_LIMIT": "32",
                "MAX_OUTPUT_BYTES": "2048",
                "MAX_SOURCE_BYTES": "4096",
                "DOCKER_BINARY": "/usr/bin/docker",
            }
        )
        self.assertTrue(config.enabled)
        self.assertEqual(
            (config.image, config.timeout_seconds, config.memory_mb, config.cpus),
            ("python@sha256:abc", 2.5, 256, 1.0),
        )
        self.assertEqual((config.pids_limit, config.max_output_bytes), (32, 2048))
        self.assertEqual((config.max_source_bytes, config.docker_binary), (4096, "/usr/bin/docker"))

    def test_invalid_settings_are_rejected_clearly(self) -> None:
        for key, value in (
            ("BACKEND", "local"),
            ("BACKEND", "subprocess"),
            ("IMAGE", "python 3.11"),
            ("TIMEOUT_SECONDS", "abc"),
            ("TIMEOUT_SECONDS", "0"),
            ("TIMEOUT_SECONDS", "600"),
            ("MEMORY_MB", "12"),
            ("MEMORY_MB", "128.5"),
            ("CPUS", "0"),
            ("CPUS", "-1"),
            ("PIDS_LIMIT", "2"),
            ("MAX_OUTPUT_BYTES", "10"),
            ("MAX_SOURCE_BYTES", "lots"),
            ("DOCKER_BINARY", "docker --host evil"),
        ):
            with self.subTest(key=key, value=value):
                with self.assertRaises(ImproperlyConfigured) as ctx:
                    RunnerConfig.from_settings({key: value})
                self.assertIn(f"PYTHON_RUNNER_{key}", str(ctx.exception))

    def test_config_is_immutable(self) -> None:
        with self.assertRaises(AttributeError):
            RunnerConfig().backend = "docker"


class RunResultTests(SimpleTestCase):
    def test_statuses(self) -> None:
        self.assertEqual(
            [status.value for status in RunStatus],
            [
                "success",
                "runtime_error",
                "timeout",
                "output_limit",
                "invalid_result",
                "runner_unavailable",
                "internal_error",
            ],
        )

    def test_results_are_immutable(self) -> None:
        run = PythonRunResult(RunStatus.SUCCESS, "out", "", 0, 10)
        call = FunctionCallResult(RunStatus.SUCCESS, value=[1])
        for result, field in ((run, "stdout"), (call, "value")):
            with self.subTest(result=type(result).__name__), self.assertRaises(AttributeError):
                setattr(result, field, "changed")
