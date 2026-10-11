"""Exercise real mount parsers, with EVERY mount syscall suppressed by strace.

Run unprivileged on Linux with toybox, busybox and strace. Unlike a mock accepting
an expected argument list, this catches a parser returning success for MS_BIND
instead of MS_SLAVE|MS_REC. No namespaces or filesystems are changed on the host.
"""

import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest


SERVICE = Path(__file__).resolve().parents[1] / "module/service.sh"


class MountParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.geteuid() == 0:
            raise RuntimeError("Run mount parser tests unprivileged, never as root")
        cls.tools = {}
        for name in ("toybox", "busybox", "strace"):
            tool = shutil.which(os.environ.get(f"VECTOR_TEST_{name.upper()}", name))
            if not tool:
                raise RuntimeError(f"Install {name} or set VECTOR_TEST_{name.upper()}")
            cls.tools[name] = tool

    def parse_mount(self, implementation, *args):
        with tempfile.TemporaryDirectory(prefix="vector-mount-parser-") as tmp:
            trace = Path(tmp) / "syscalls"
            result = subprocess.run(
                [self.tools["strace"], "-f", "-o", str(trace),
                 "-e", "trace=mount,getuid,geteuid", "-e", "inject=mount:retval=0",
                 "-e", "inject=getuid:retval=0", "-e", "inject=geteuid:retval=0",
                 self.tools[implementation], "mount", *args],
                capture_output=True, text=True, timeout=10,
            )
            calls = [line for line in trace.read_text().splitlines() if "mount(" in line]
            # Even a regression in the command/parser must never reach a real mount syscall.
            for call in calls:
                self.assertIn("(INJECTED)", call)
            return result, calls

    def test_production_command_requests_only_recursive_slave_propagation(self):
        namespace = re.search(r"unshare -m sh -c '([^']+)'", SERVICE.read_text())
        self.assertIsNotNone(namespace)
        command, separator, _ = namespace[1].partition(" && ")
        self.assertTrue(separator, "daemon must run only after successful isolation")
        argv = shlex.split(command)
        # Explicit Android binary avoids BusyBox ash standalone/PATH applet substitution.
        self.assertEqual(argv, ["/system/bin/mount", "-t", "rootfs", "-o", "rslave", "rootfs", "/"])
        result, calls = self.parse_mount("toybox", *argv[1:])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 1, calls)
        # strace may print the type as an opaque pointer: the kernel ignores it
        # for a propagation operation, rather than mounting that filesystem type.
        self.assertIn('mount("rootfs", "/",', calls[0])
        for flag in ("MS_SLAVE", "MS_REC"):
            self.assertIn(flag, calls[0])
        for flag in ("MS_BIND", "MS_REMOUNT", "MS_MOVE", "MS_SHARED"):
            self.assertNotIn(flag, calls[0])

    def test_old_single_operand_form_never_requests_slave_propagation(self):
        _, calls = self.parse_mount("toybox", "--make-rslave", "/")
        # Android without /etc/fstab fails before mount(). A Linux host with a
        # root fstab entry can instead try mounting it. Neither is propagation.
        self.assertFalse(any("MS_SLAVE" in call for call in calls), calls)

    def test_two_directory_operands_are_a_false_success_not_isolation(self):
        result, calls = self.parse_mount("toybox", "-o", "rslave", "/", "/")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 1, calls)
        self.assertIn("MS_BIND", calls[0])
        self.assertNotIn("MS_REC", calls[0])

    def test_busybox_and_toybox_propagation_option_spellings_differ(self):
        result, calls = self.parse_mount("busybox", "--make-rslave", "/")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 1, calls)
        self.assertIn("MS_SLAVE", calls[0])
        self.assertIn("MS_REC", calls[0])
        # Even the documented "rslave" option is not the BusyBox parser key;
        # using the Android form via PATH would try mounting a new filesystem.
        _, calls = self.parse_mount("busybox", "-t", "rootfs", "-o", "rslave", "rootfs", "/")
        self.assertEqual(len(calls), 1, calls)
        self.assertNotIn("MS_SLAVE", calls[0])
        self.assertIn('"rslave"', calls[0])


if __name__ == "__main__":
    unittest.main()
