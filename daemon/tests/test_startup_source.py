"""Static guards for the startup safety contract."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DAEMON = ROOT / "src/main/kotlin/org/matrix/vector/daemon"


class StartupSourceTest(unittest.TestCase):
    def test_initialization_waits_and_fails_with_diagnostics_on_framework_death(self):
        source = (DAEMON / "VectorDaemon.kt").read_text()
        self.assertIn("awaitLiveCoreServices()", source)
        self.assertIn("startupPhase(\"initialize ActivityThread\")", source)
        self.assertIn("full stack before exit", source)
        self.assertNotIn("initializeActivityThread(", source)
        self.assertNotIn("waitForSystemService(", source)

    def test_startup_log_is_exported_outside_rotated_log_tree(self):
        filesystem = (DAEMON / "data/FileSystem.kt").read_text()
        self.assertIn('addFile("startup.log", basePath.resolve("startup.log").toFile())', filesystem)
        self.assertIn('addFile("startup.log.old", basePath.resolve("startup.log.old").toFile())', filesystem)

    def test_launcher_never_contains_restart_loop(self):
        launcher = (ROOT.parent / "zygisk/module/daemon").read_text()
        self.assertNotIn("ctl.restart", launcher)
        self.assertNotIn("stop; start", launcher)


if __name__ == "__main__":
    unittest.main()
