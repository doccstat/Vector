"""Host tests for the Android-independent startup diagnostics/readiness helpers."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

DAEMON = Path(__file__).resolve().parents[1]
JAVA = DAEMON / "src/main/java/org/matrix/vector/daemon/env"


class StartupHelpersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("javac") or not shutil.which("java"):
            raise RuntimeError("JDK required")
        cls.build = tempfile.TemporaryDirectory(prefix="vector-startup-classes-")
        cls.addClassCleanup(cls.build.cleanup)
        subprocess.run(
            ["javac", "-d", cls.build.name,
             str(JAVA / "CoreServiceGate.java"),
             str(JAVA / "StartupLog.java")],
            check=True, timeout=30,
        )
        cls.probe = Path(cls.build.name) / "StartupHelpersProbe.java"
        cls.probe.write_text(r'''
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import org.matrix.vector.daemon.env.CoreServiceGate;
import org.matrix.vector.daemon.env.StartupLog;

public final class StartupHelpersProbe {
  public static void main(String[] args) throws Exception {
    List<String> calls = new ArrayList<>();
    int[] round = {0};
    CoreServiceGate.awaitReady(
        new String[] {"package", "activity"},
        name -> round[0] >= 2,
        missing -> { calls.add(missing); round[0]++; });
    if (!calls.equals(List.of("package", "package"))) throw new AssertionError(calls);

    Path dir = Files.createTempDirectory("vector-startup-log-");
    try (StartupLog log = StartupLog.open(dir)) {
      log.phase("first");
      log.phase("second");
      log.failure(Thread.currentThread(), new IllegalStateException("diagnostic"));
    }
    String content = Files.readString(dir.resolve("startup.log"));
    if (!content.contains("Phase: first") || !content.contains("Phase: second") ||
        !content.contains("IllegalStateException: diagnostic")) throw new AssertionError(content);
    try (StartupLog ignored = StartupLog.open(dir)) {}
    if (!Files.exists(dir.resolve("startup.log.old"))) throw new AssertionError("rotation");
    System.out.println("OK");
  }
}
''')
        subprocess.run(["javac", "-cp", cls.build.name, "-d", cls.build.name, str(cls.probe)], check=True)

    def test_helpers(self):
        result = subprocess.run(
            ["java", "-cp", self.build.name, "StartupHelpersProbe"],
            check=True, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.stdout.strip(), "OK")


if __name__ == "__main__":
    unittest.main()
