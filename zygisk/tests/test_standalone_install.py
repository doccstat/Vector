"""Vector-only install -> boot-launch contract; no companion root app or device.

Executes customize.sh, service.sh and daemon. Root-manager installer helpers,
SELinux, namespaces, mounts and app_process are simulated. ZIP extraction,
checksums, ABI selection, shell arguments and file modes are real. This does not
emulate Android/ART or certify a physical root-manager/device combination.
"""

import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
import unittest
import zipfile


MODULE = Path(__file__).resolve().parents[1] / "module"
SYSTEM_FILE = "u:object_r:system_file:s0"
XPOSED_FILE = "u:object_r:xposed_file:s0"

# The shared installer API provided by Magisk, KernelSU and APatch. Contexts
# deliberately have no default: the package must explicitly request its labels.
INSTALL_HELPERS = r'''
ui_print() { printf '%s\n' "$*"; }
abort() { printf '%s\n' "$*" >&2; exit 1; }
grep_prop() {
    [ -n "$2" ] || return 0
    grep "^$1=" "$2" | cut -d= -f2-
}
set_perm_recursive() {
    printf 'recursive|%s|%s|%s|%s|%s|%s\n' "$1" "$2" "$3" "$4" "$5" "$6" >> "$PERMISSIONS"
    find "$1" -type d -exec chmod "$4" {} +
    find "$1" -type f -exec chmod "$5" {} +
}
set_perm() {
    printf 'file|%s|%s|%s|%s|%s\n' "$1" "$2" "$3" "$4" "$5" >> "$PERMISSIONS"
    chmod "$4" "$1"
}
. "$CUSTOMIZE"
'''


class StandaloneInstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vector-install-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        # No Android absolute path in the fixture is allowed to reach the host.
        self.customize = self.root / "customize.sh"
        self.customize.write_text(
            (MODULE / "customize.sh").read_text().replace("/data/adb", str(self.root / "adb"))
        )
        self.zygote = self.root / "zygote"
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.bind(str(self.zygote))
        self.addCleanup(self.sock.close)
        self.trace = self.root / "trace"
        self.app_args = self.root / "app-args.json"
        self.permissions = self.root / "permissions"
        self.env = dict(
            os.environ,
            PATH=f"{self.tools}:/usr/bin:/bin",
            TRACE=str(self.trace), APP_ARGS=str(self.app_args),
            PERMISSIONS=str(self.permissions), CUSTOMIZE=str(self.customize),
        )
        for variable in ("KSU", "APATCH", "MAGISK_VER_CODE", "ASH_STANDALONE"):
            self.env.pop(variable, None)
        self.command("unshare", '''
[ "$1" = -m ] || exit 91
shift
printf 'namespace\\n' >> "$TRACE"
export VECTOR_TEST_NAMESPACE=1
exec "$@"
''')
        self.command("mount", '''
[ "$VECTOR_TEST_NAMESPACE" = 1 ] || exit 92
case "$*" in
  '--make-rslave /') printf 'rslave\\n' >> "$TRACE" ;;
  'tmpfs -t tmpfs /data/resource-cache') printf 'resource-cache\\n' >> "$TRACE" ;;
  *) exit 93 ;;
esac
''')
        self.command("getprop", '[ "$1" = ro.build.version.sdk ] && echo "$TEST_SDK"')
        self.command("log", 'printf "log:%s\\n" "$*" >> "$TRACE"')
        self.command("app_process", '''
printf 'app_process\\n' >> "$TRACE"
exec python3 -c 'import json,os,sys; open(os.environ["APP_ARGS"],"w").write(json.dumps(sys.argv[1:]))' "$@"
''')

    def command(self, name, body):
        path = self.tools / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
        return path

    def archive(self, debug=False, corrupt=None):
        payloads = {
            name: (MODULE / name).read_bytes()
            for name in (
                "action.sh", "service.sh", "uninstall.sh", "sepolicy.rule", "cli", "system.prop"
            )
        }
        # Only platform-path substitution for host execution, not changes to control flow.
        payloads["daemon"] = (
            (MODULE / "daemon").read_text()
            .replace("#!/system/bin/sh", "#!/bin/sh", 1)
            .replace("@DEBUG@", "true" if debug else "false")
            .replace("/system/bin/app_process", shlex.quote(str(self.tools / "app_process")))
            .replace("/dev/socket/zygote", str(self.zygote))
            .replace("/data/local/tmp/daemon.apk", str(self.root / "no-debug-override.apk"))
        ).encode()
        payloads.update({
            "module.prop": b"id=zygisk_vector\nversion=test\n",
            "daemon.apk": b"fixture-daemon-apk",
            "manager.apk": b"fixture-manager-apk",
            "framework/vector.dex": b"fixture-framework-dex",
        })
        for abi in ("arm64-v8a", "armeabi-v7a", "x86", "x86_64"):
            for prefix, name in (("lib", "libzygisk.so"), ("bin", "dex2oat"), ("bin", "liboat_hook.so")):
                payloads[f"{prefix}/{abi}/{name}"] = f"fixture:{abi}:{name}".encode()
        archive = self.root / "module.zip"
        with zipfile.ZipFile(archive, "w") as z:
            for name, data in payloads.items():
                z.writestr(name, b"CORRUPTED" if name == corrupt else data)
                z.writestr(name + ".sha256", hashlib.sha256(data).hexdigest())
        return archive

    def install(self, archive, manager, arch, api, name="module with spaces"):
        module = self.root / name
        module.mkdir()
        installer_tmp = self.root / (name + " installer")
        installer_tmp.mkdir()
        with zipfile.ZipFile(archive) as z:
            (installer_tmp / "module.prop").write_bytes(z.read("module.prop"))
        flags = {
            "magisk": {"MAGISK_VER_CODE": "30000"},
            "kernelsu": {"KSU": "true"},
            "apatch": {"APATCH": "true"},
        }[manager]
        env = dict(
            self.env, **flags, ZIPFILE=str(archive), MODPATH=str(module),
            TMPDIR=str(installer_tmp), ARCH=arch, API=str(api),
            IS64BIT="true" if arch in ("arm64", "x64") else "false",
        )
        result = subprocess.run(
            ["sh"], input=INSTALL_HELPERS, env=env, capture_output=True, text=True, timeout=15,
        )
        return result, module, env

    def launch(self, module, env, api):
        result = subprocess.run(
            ["sh", str(module / "service.sh"), "argument with spaces", "--extra=value"],
            cwd=self.root, env=dict(env, TEST_SDK=str(api)),
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.app_args.exists(), result.stdout + result.stderr)
        trace = self.trace.read_text()
        self.assertTrue(trace.startswith("namespace\nrslave\nresource-cache\n"), trace)
        self.assertEqual(trace.count("app_process\n"), 1)
        args = json.loads(self.app_args.read_text())
        self.assertEqual(args[0], f"-Djava.class.path={module}/daemon.apk")
        self.assertEqual(args[-6:], [
            "/system/bin", "--nice-name=vectord", "org.matrix.vector.daemon.VectorDaemon",
            "--system-server-max-retry=3", "argument with spaces", "--extra=value",
        ])
        return args

    def test_install_and_launch_without_a_companion_app(self):
        archive = self.archive()
        # ARM/x86, 32/64-bit; pre-dex2oat-wrapper and current API levels.
        for manager in ("magisk", "kernelsu", "apatch"):
            for arch, api, abis in (
                ("arm", 27, {"armeabi-v7a.so"}),
                ("arm64", 37, {"armeabi-v7a.so", "arm64-v8a.so"}),
                ("x86", 28, {"x86.so"}),
                ("x64", 29, {"x86.so", "x86_64.so"}),
            ):
                with self.subTest(manager=manager, arch=arch, api=api):
                    name = f"{manager} {arch} module"
                    result, module, env = self.install(archive, manager, arch, api, name)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual({p.name for p in (module / "zygisk").iterdir()}, abis)
                    self.assertEqual((module / "daemon").stat().st_mode & 0o777, 0o744)
                    self.assertEqual((module / "manager.apk").stat().st_mode & 0o777, 0o644)
                    labels = self.permissions.read_text()
                    self.assertIn(f"recursive|{module}|0|0|0755|0644|{SYSTEM_FILE}", labels)
                    if api >= 29:
                        self.assertIn(f"recursive|{module}/bin|0|2000|0755|0755|{XPOSED_FILE}", labels)
                    else:
                        self.assertTrue((module / "system.prop").exists())
                        self.assertFalse((module / "bin").exists())
                    args = self.launch(module, env, api)
                    self.assertEqual(args[1:-6], [])  # Release builds add no debug VM flags.
                    self.app_args.unlink()
                    self.trace.unlink()

    def test_debug_launch_preserves_sdk_specific_options_and_arguments(self):
        archive = self.archive(debug=True)
        for api in (27, 28, 37):
            with self.subTest(api=api):
                result, module, env = self.install(archive, "kernelsu", "arm64", api, f"debug {api}")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                args = self.launch(module, env, api)
                expected = (
                    ["-Xrunjdwp:transport=dt_android_adb,suspend=n,server=y"] if api == 27
                    else ["-XjdwpProvider:adbconnection", "-XjdwpOptions:suspend=n,server=y"]
                )
                if api in (27, 28):
                    expected += ["-Xcompiler-option", "--debuggable"]
                self.assertEqual(args[1:-6], expected)
                self.app_args.unlink()
                self.trace.unlink()

    def test_corrupt_launcher_is_rejected_by_standalone_installer(self):
        result, _, _ = self.install(self.archive(corrupt="service.sh"), "magisk", "arm64", 37)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Failed to verify service.sh", result.stdout + result.stderr)
        self.assertFalse(self.app_args.exists())

    def test_boot_files_have_no_device_or_root_app_dependency(self):
        for name in ("customize.sh", "service.sh", "daemon"):
            with self.subTest(file=name):
                text = (MODULE / name).read_text()
                for external in (
                    "module_compat.sh", "netfix.sh", "RMP_", "com.lixingchi.ghostlock",
                    "/data/adb/ksu/bin/busybox", "/data/adb/magisk/busybox", "yogi",
                ):
                    self.assertNotIn(external, text)


if __name__ == "__main__":
    unittest.main()
