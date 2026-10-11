"""Real process-lock regression tests. Requires a JDK on PATH; no Android SDK."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile
import unittest


DAEMON = Path(__file__).resolve().parents[1]
LOCK = DAEMON / "src/main/java/org/matrix/vector/daemon/data/DaemonLock.java"
PROBE = Path(__file__).with_name("DaemonLockProbe.java")


class DaemonLockTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("javac") or not shutil.which("java"):
            raise RuntimeError("JDK required: put javac and java on PATH")
        cls.build = tempfile.TemporaryDirectory(prefix="vector-lock-classes-")
        cls.addClassCleanup(cls.build.cleanup)
        subprocess.run(
            ["javac", "-d", cls.build.name, str(LOCK), str(PROBE)], check=True, timeout=30,
        )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vector-lock-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "lock"

    def probe(self, path=None):
        process = subprocess.Popen(
            ["java", "-cp", self.build.name, "DaemonLockProbe", str(path or self.path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.addCleanup(self.stop, process)
        return process

    def stop(self, process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)

    def ask(self, process, command="acquire"):
        process.stdin.write(command + "\n")
        process.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout=10), "Lock probe hung")
        response = process.stdout.readline().strip()
        self.assertTrue(response, "Lock probe exited without a response")
        return response

    def test_sigkill_and_leftover_file_do_not_block_next_process(self):
        # A cold boot/restore may leave both historical files. Neither proves ownership.
        (self.root / ".vectord-start").mkdir()
        self.path.touch(mode=0o600)
        inode = self.path.stat().st_ino
        owner = self.probe()
        self.assertEqual(self.ask(owner), "ACQUIRED")
        contender = self.probe()
        self.assertEqual(self.ask(contender), "HELD")
        owner.kill()  # No exit traps or cleanup run.
        owner.wait(timeout=10)
        self.assertEqual(self.ask(contender), "ACQUIRED")
        self.assertEqual(self.path.stat().st_ino, inode)
        self.assertTrue((self.root / ".vectord-start").is_dir())

    def test_normal_exit_releases_ownership_without_deleting_file(self):
        owner = self.probe()
        self.assertEqual(self.ask(owner), "ACQUIRED")
        inode = self.path.stat().st_ino
        owner.communicate(timeout=10)  # EOF is a normal JVM exit, not a kill.
        self.assertEqual(owner.returncode, 0)
        self.assertEqual(self.ask(self.probe()), "ACQUIRED")
        self.assertEqual(self.path.stat().st_ino, inode)

    def test_simultaneous_launches_have_exactly_one_owner(self):
        contenders = [self.probe() for _ in range(8)]
        with ThreadPoolExecutor(max_workers=len(contenders)) as pool:
            results = list(pool.map(self.ask, contenders))
        self.assertEqual(results.count("ACQUIRED"), 1, results)
        self.assertEqual(results.count("HELD"), 7, results)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_owner_recheck_preserves_lock(self):
        owner = self.probe()
        self.assertEqual(self.ask(owner), "ACQUIRED")
        self.assertEqual(self.ask(owner), "ACQUIRED")
        self.assertEqual(self.ask(self.probe()), "HELD")

    def test_contention_closes_unused_channels(self):
        self.assertEqual(self.ask(self.probe()), "ACQUIRED")
        contender = self.probe()
        self.assertEqual(self.ask(contender), "HELD")  # Warm class loading before counting FDs.
        before = int(self.ask(contender, "fds"))
        self.assertEqual(self.ask(contender, "retry"), "HELD")
        self.assertEqual(int(self.ask(contender, "fds")), before)

    def test_io_error_is_not_reported_as_another_daemon(self):
        self.path.mkdir()  # Cannot open a directory as a writable lock file.
        contender = self.probe()
        self.assertTrue(self.ask(contender).startswith("ERROR:"))
        self.path.rmdir()
        self.assertEqual(self.ask(contender), "ACQUIRED")

    def test_missing_parent_can_be_repaired_and_retried(self):
        path = self.root / "missing/lock"
        contender = self.probe(path)
        self.assertTrue(self.ask(contender).startswith("ERROR:"))
        path.parent.mkdir()
        self.assertEqual(self.ask(contender), "ACQUIRED")


if __name__ == "__main__":
    unittest.main()
