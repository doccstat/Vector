"""Real JVM startup helper tests; no Android/ART or framework restart simulation."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

DAEMON = Path(__file__).resolve().parents[1]
JAVA = DAEMON / "src/main/java/org/matrix/vector/daemon/env"
PROBE = Path(__file__).with_name("StartupHelpersProbe.java")


class StartupHelpersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("javac") or not shutil.which("java"):
            raise RuntimeError("JDK required")
        cls.build = tempfile.TemporaryDirectory(prefix="vector-startup-classes-")
        cls.addClassCleanup(cls.build.cleanup)
        subprocess.run(
            ["javac", "--release", "8", "-d", cls.build.name,
             str(JAVA / "CoreServiceGate.java"), str(JAVA / "StartupLog.java"), str(PROBE)],
            check=True, timeout=30,
        )

    def check_probe(self, scenario):
        # Pass the owned directory to Java; do not leak Files.createTempDirectory outputs.
        with tempfile.TemporaryDirectory(prefix="vector-startup-data-") as directory:
            result = subprocess.run(
                ["java", "-cp", self.build.name, "StartupHelpersProbe", scenario, directory],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), "OK")

    def test_live_services_need_no_wait(self):
        self.check_probe("ready")

    def test_wait_rechecks_services_that_were_previously_alive(self):
        self.check_probe("recheck")

    def test_probe_errors_are_not_swallowed_or_retried(self):
        self.check_probe("probe-error")

    def test_wait_interruption_propagates(self):
        self.check_probe("interrupt")

    def test_phase_cause_and_suppressed_stacks_are_flushed_privately(self):
        self.check_probe("log")

    def test_rotation_retains_only_the_previous_start(self):
        self.check_probe("rotate")

    def test_log_budget_reserves_space_for_fatal_stack(self):
        self.check_probe("bounded")

    def test_existing_symlink_is_rejected_without_touching_target(self):
        self.check_probe("symlink")

    def test_parent_must_already_exist(self):
        self.check_probe("missing-parent")

    def test_writes_use_owned_descriptor_not_path_reopen(self):
        self.check_probe("descriptor")


if __name__ == "__main__":
    unittest.main()
