"""Host-only launcher tests; namespace/mount/process commands are mocked."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SERVICE = Path(__file__).resolve().parents[1] / "module/service.sh"
DAEMON = SERVICE.with_name("daemon")


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vector-service-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = self.root / "module with spaces"
        self.module.mkdir()
        self.service = self.module / "service.sh"
        self.stale_lock = self.root / "state/.vectord-start"
        self.stale_lock.mkdir(parents=True)
        self.service.write_text(
            SERVICE.read_text().replace("/data/adb/lspd", str(self.stale_lock.parent))
        )
        self.trace = self.root / "trace"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin", TRACE=str(self.trace))
        # A process name is not lock ownership, even if pidof finds a match.
        self.command(self.bin / "pidof", 'exit "${RUNNING:-0}"')
        self.command(self.bin / "log", 'printf "log:%s\\n" "$*" >> "$TRACE"')
        self.command(self.bin / "unshare", '''
[ "$1" = -m ] || exit 91
printf 'unshare\\n' >> "$TRACE"
[ "${UNSHARE_RESULT:-0}" = 0 ] || exit "$UNSHARE_RESULT"
shift
exec "$@"
''')
        self.command(self.bin / "mount", '''
[ "$#" = 2 ] && [ "$1" = --make-rslave ] && [ "$2" = / ] || exit 92
printf 'mount\\n' >> "$TRACE"
exit "${MOUNT_RESULT:-0}"
''')
        self.command(self.module / "daemon", '''
printf 'daemon\\n' >> "$TRACE"
printf '<%s>\\n' "$@" >> "$TRACE"
exit "${DAEMON_RESULT:-0}"
''')

    def command(self, path, body):
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def run_service(self, **env):
        # The pipe stays open in the background launcher until it exits. communicate() therefore
        # waits for both the stage script and the mocked daemon, with no polling or host mounts.
        result = subprocess.run(
            ["sh", str(self.service), "argument with spaces", "--extra=value"],
            env=dict(self.env, **env), capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.last_stderr = result.stderr
        return self.trace.read_text() if self.trace.exists() else ""

    def test_namespace_is_private_before_daemon_and_arguments_survive(self):
        trace = self.run_service()
        self.assertTrue(trace.startswith("unshare\nmount\ndaemon\n"), trace)
        self.assertIn("<--system-server-max-retry=3>", trace)
        self.assertIn("<argument with spaces>", trace)
        self.assertIn("<--extra=value>", trace)
        self.assertNotIn("log:", trace)

    def test_process_name_and_stale_directory_do_not_suppress_lock_attempt(self):
        self.assertIn("daemon\n", self.run_service(RUNNING="0"))
        self.assertTrue(self.stale_lock.is_dir())
        self.assertNotIn("pidof", self.service.read_text())

    def test_mount_failure_never_launches_daemon_and_is_reported(self):
        trace = self.run_service(MOUNT_RESULT="1")
        self.assertTrue(trace.startswith("unshare\nmount\n"), trace)
        self.assertNotIn("daemon\n", trace)
        self.assertIn("log:-p e -t Vector Daemon launch failed (exit 1)", trace)
        self.assertIn("Daemon launch failed (exit 1)", self.last_stderr)

    def test_unshare_failure_never_mounts_or_launches_daemon(self):
        trace = self.run_service(UNSHARE_RESULT="7")
        self.assertNotIn("mount\n", trace)
        self.assertNotIn("daemon\n", trace)
        self.assertIn("log:-p e -t Vector Daemon launch failed (exit 7)", trace)

    def test_daemon_failure_is_reported_without_automatic_restarts(self):
        trace = self.run_service(DAEMON_RESULT="23")
        self.assertEqual(trace.count("daemon\n"), 1)
        self.assertIn("log:-p e -t Vector Daemon launch failed (exit 23)", trace)

    def test_resource_cache_mount_failure_is_fatal(self):
        self.command(self.bin / "mount", "exit 1")
        result = subprocess.run(
            ["sh", str(DAEMON)], env=self.env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cannot isolate /data/resource-cache", result.stderr)

    def test_failed_launch_does_not_leave_a_shell_singleton_lock(self):
        self.run_service(MOUNT_RESULT="1")
        self.trace.unlink()
        self.assertIn("daemon\n", self.run_service())
        self.assertNotIn(".vectord-start", self.service.read_text())


if __name__ == "__main__":
    unittest.main()
