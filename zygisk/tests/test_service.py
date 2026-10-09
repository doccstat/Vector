"""Host-only launcher tests; namespace/mount/process commands are mocked."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SERVICE = Path(__file__).resolve().parents[1] / "module/service.sh"


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vector-service-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = self.root / "module with spaces"
        self.module.mkdir()
        self.service = self.module / "service.sh"
        self.service.write_bytes(SERVICE.read_bytes())
        self.trace = self.root / "trace"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin", TRACE=str(self.trace))
        self.command(self.bin / "pidof", 'exit "${RUNNING:-1}"')
        self.command(self.bin / "unshare", '''
[ "$1" = -m ] || exit 91
printf 'unshare\\n' >> "$TRACE"
shift
exec "$@"
''')
        self.command(self.bin / "mount", '''
[ "$#" = 2 ] && [ "$1" = --make-rslave ] && [ "$2" = / ] || exit 92
printf 'mount\\n' >> "$TRACE"
exit "${MOUNT_RESULT:-0}"
''')
        self.command(self.module / "daemon", 'printf "daemon\\n<%s>\\n" "$@" >> "$TRACE"')

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
        return self.trace.read_text() if self.trace.exists() else ""

    def test_namespace_is_private_before_daemon_and_arguments_survive(self):
        trace = self.run_service()
        self.assertTrue(trace.startswith("unshare\nmount\ndaemon\n"), trace)
        self.assertIn("<--system-server-max-retry=3>", trace)
        self.assertIn("<argument with spaces>", trace)
        self.assertIn("<--extra=value>", trace)

    def test_running_daemon_skips_namespace_and_mount(self):
        self.assertEqual(self.run_service(RUNNING="0"), "")

    def test_mount_failure_never_launches_daemon(self):
        self.assertEqual(self.run_service(MOUNT_RESULT="1"), "unshare\nmount\n")

    def test_failed_launch_does_not_leave_a_shell_singleton_lock(self):
        self.run_service(MOUNT_RESULT="1")
        self.trace.unlink()
        self.assertIn("daemon\n", self.run_service())
        self.assertNotIn(".vectord-start", self.service.read_text())


if __name__ == "__main__":
    unittest.main()
