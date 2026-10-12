import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.matrix.vector.daemon.env.CoreServiceGate;
import org.matrix.vector.daemon.env.StartupLog;

/** Real startup helpers; no Android, Binder, mounts, logd, or daemon execution. */
public final class StartupHelpersProbe {
    public static void main(String[] args) throws Exception {
        Path dir = Paths.get(args[1]);
        switch (args[0]) {
            case "ready": {
                List<String> probes = new ArrayList<>();
                CoreServiceGate.awaitReady(new String[]{"package", "activity", "user", "appops"},
                        name -> { probes.add(name); return true; },
                        name -> { throw new AssertionError("Unexpected wait"); });
                require(probes.equals(Arrays.asList("package", "activity", "user", "appops")));
                break;
            }
            case "recheck": {
                int[] round = {0};
                List<String> waits = new ArrayList<>();
                // Package is initially alive, then dies while waiting for activity.
                CoreServiceGate.awaitReady(new String[]{"package", "activity"},
                        name -> round[0] >= 2 || (round[0] == 0) == name.equals("package"),
                        name -> { waits.add(name); round[0]++; });
                require(waits.equals(Arrays.asList("activity", "package")));
                break;
            }
            case "probe-error": {
                RuntimeException expected = new SecurityException("not a readiness failure");
                try {
                    CoreServiceGate.awaitReady(new String[]{"package"},
                            name -> { throw expected; },
                            name -> { throw new AssertionError("Must not retry"); });
                    throw new AssertionError("Swallowed error");
                } catch (RuntimeException actual) {
                    require(actual == expected);
                }
                break;
            }
            case "interrupt": {
                try {
                    CoreServiceGate.awaitReady(new String[]{"package"}, name -> false,
                            name -> { throw new InterruptedException("cancelled"); });
                    throw new AssertionError("Ignored interruption");
                } catch (InterruptedException expected) {
                    require(expected.getMessage().equals("cancelled"));
                }
                break;
            }
            case "log": {
                try (StartupLog log = StartupLog.open(dir)) {
                    log.phase("framework initialization");
                    IOException cause = new IOException("underlying Binder died");
                    cause.addSuppressed(new IllegalStateException("suppressed evidence"));
                    log.failure(Thread.currentThread(), new RuntimeException("startup failed", cause));
                    // Read BEFORE close: a fatal exit need not run orderly cleanup.
                    String content = text(dir.resolve("startup.log"));
                    require(content.contains("during framework initialization"));
                    require(content.contains("RuntimeException: startup failed"));
                    require(content.contains("Caused by: java.io.IOException: underlying Binder died"));
                    require(content.contains("Suppressed: java.lang.IllegalStateException"));
                    require(content.contains("StartupHelpersProbe.main"));
                    require(Files.getPosixFilePermissions(dir.resolve("startup.log")).equals(
                            PosixFilePermissions.fromString("rw-------")));
                }
                break;
            }
            case "rotate": {
                byte[] previous = null;
                for (int i = 0; i < 3; i++) {
                    try (StartupLog log = StartupLog.open(dir)) {
                        if (previous != null) require(Arrays.equals(previous,
                                Files.readAllBytes(dir.resolve("startup.log.old"))));
                        log.phase("launch " + i);
                    }
                    previous = Files.readAllBytes(dir.resolve("startup.log"));
                }
                try (java.util.stream.Stream<Path> files = Files.list(dir)) {
                    require(files.count() == 2);
                }
                break;
            }
            case "bounded": {
                char[] huge = new char[256 * 1024];
                Arrays.fill(huge, 'x');
                try (StartupLog log = StartupLog.open(dir)) {
                    log.phase(new String(huge));
                    require(Files.size(dir.resolve("startup.log")) <= 64 * 1024);
                    log.phase("final phase");
                    log.failure(Thread.currentThread(), new IOException("fatal-marker " + new String(huge)));
                    require(Files.size(dir.resolve("startup.log")) == 128 * 1024);
                    log.failure(Thread.currentThread(), new IOException("another failure"));
                }
                String content = text(dir.resolve("startup.log"));
                require(Files.size(dir.resolve("startup.log")) == 128 * 1024);
                require(content.contains("during final phase"));
                require(content.contains("fatal-marker"));
                require(content.endsWith("[diagnostic truncated]\n"));
                break;
            }
            case "symlink": {
                Path target = dir.resolve("target");
                Files.write(target, new byte[]{42});
                Files.createSymbolicLink(dir.resolve("startup.log"), target);
                try {
                    StartupLog.open(dir).close();
                    throw new AssertionError("Followed a symlink");
                } catch (IOException expected) {
                    require(Arrays.equals(Files.readAllBytes(target), new byte[]{42}));
                    require(!Files.exists(dir.resolve("startup.log.old")));
                }
                break;
            }
            case "missing-parent": {
                Path missing = dir.resolve("missing");
                try {
                    StartupLog.open(missing).close();
                    throw new AssertionError("Created unprotected parent");
                } catch (IOException expected) {
                    require(!Files.exists(missing));
                }
                break;
            }
            case "descriptor": {
                Path original = Files.createDirectory(dir.resolve("original"));
                try (StartupLog log = StartupLog.open(original)) {
                    Files.move(original, dir.resolve("moved"));
                    log.phase("write through owned descriptor");
                    log.failure(Thread.currentThread(), new IOException("still writable"));
                    require(text(dir.resolve("moved/startup.log")).contains("still writable"));
                    require(!Files.exists(original));
                }
                break;
            }
            default: throw new AssertionError("Unknown probe: " + args[0]);
        }
        System.out.println("OK");
    }

    private static String text(Path path) throws IOException {
        return new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
    }

    private static void require(boolean condition) {
        if (!condition) throw new AssertionError();
    }
}
