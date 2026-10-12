"""Static wiring guards, not Android execution tests; helpers run in separate JVM tests."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DAEMON = ROOT / "src/main/kotlin/org/matrix/vector/daemon"


def code(path):
    # Assertions must not pass just because a comment describes the desired behavior.
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(), flags=re.S)


class StartupSourceTest(unittest.TestCase):
    def test_early_proxy_precedes_readiness_and_one_framework_initialization(self):
        source = code(DAEMON / "VectorDaemon.kt")
        proxy = source.index("SystemServerService.registerProxyService(proxyServiceName)")
        wait = source.index("awaitLiveCoreServices()")
        initialize = source.index("ActivityThread.systemMain()")
        self.assertLess(proxy, wait)
        self.assertLess(wait, initialize)
        self.assertLess(initialize, source.index("applyNotificationWorkaround()", initialize))
        self.assertEqual(source.count("ActivityThread.systemMain()"), 1)
        gate = source.split("private fun awaitLiveCoreServices()", 1)[1].split(
            "private fun sendToBridge(", 1
        )[0]
        self.assertIn("CoreServiceGate.awaitReady(", gate)
        self.assertIn("service?.pingBinder() == true", gate)
        self.assertIn("if (service != null && !alive) clearSystemCaches()", gate)
        self.assertNotIn("waitForSystemService(", source)
        self.assertNotIn("restartSystemServer(", source[:source.index("private fun sendToBridge(")])

    def test_lock_loser_cannot_rotate_diagnostics_and_fatal_handler_exits(self):
        source = code(DAEMON / "VectorDaemon.kt")
        lock = source.index("FileSystem.tryLock()")
        duplicate_exit = source.index("kotlin.system.exitProcess(0)", lock)
        journal = source.index("StartupLog.open(FileSystem.basePath)")
        handler = source.index("Thread.setDefaultUncaughtExceptionHandler")
        self.assertLess(duplicate_exit, journal)
        self.assertLess(journal, handler)
        self.assertLess(handler, source.index("LogcatMonitor.start()"))
        self.assertIn("startupLog?.failure(thread, error)", source[handler:])
        self.assertRegex(source[handler:], r"finally\s*\{\s*kotlin.system.exitProcess\(1\)")

    def test_startup_log_is_exported_outside_rotated_log_tree(self):
        filesystem = code(DAEMON / "data/FileSystem.kt")
        for name in ("startup.log", "startup.log.old"):
            self.assertIn(f'addFile("{name}", basePath.resolve("{name}").toFile())', filesystem)

    def test_launcher_never_contains_restart_loop(self):
        launcher = (ROOT.parent / "zygisk/module/daemon").read_text()
        self.assertNotIn("ctl.restart", launcher)
        self.assertNotIn("stop; start", launcher)


if __name__ == "__main__":
    unittest.main()
