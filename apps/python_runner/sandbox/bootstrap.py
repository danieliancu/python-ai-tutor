"""Runs INSIDE the sandbox container only, never in the Django process.

Copies the run's private fixture files into the writable working directory, then runs the
target script (the learner program or the function harness) exactly as if it were started
directly.
"""

import os
import runpy
import shutil
import sys

FIXTURE_DIR = "/sandbox/fixtures"


def main() -> None:
    target = sys.argv[1]
    if os.path.isdir(FIXTURE_DIR):
        for name in sorted(os.listdir(FIXTURE_DIR)):
            shutil.copyfile(os.path.join(FIXTURE_DIR, name), name)
    sys.argv = [target]
    runpy.run_path(target, run_name="__main__")


if __name__ == "__main__":
    main()
