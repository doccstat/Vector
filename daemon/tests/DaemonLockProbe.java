import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;
import org.matrix.vector.daemon.data.DaemonLock;

/** Separate JVM per contender, so tests exercise the real OS lock rather than JVM overlap checks. */
public final class DaemonLockProbe {
    public static void main(String[] args) throws Exception {
        DaemonLock lock = new DaemonLock(Path.of(args[0]));
        BufferedReader input = new BufferedReader(new InputStreamReader(System.in));
        String command;
        while ((command = input.readLine()) != null) {
            try {
                if (command.equals("fds")) {
                    try (Stream<Path> files = Files.list(Path.of("/proc/self/fd"))) {
                        System.out.println(files.count());
                    }
                } else if (command.equals("retry")) {
                    for (int i = 0; i < 1000; i++) {
                        if (lock.tryAcquire()) throw new AssertionError("Unexpected ownership");
                    }
                    System.out.println("HELD");
                } else if (command.equals("acquire")) {
                    System.out.println(lock.tryAcquire() ? "ACQUIRED" : "HELD");
                } else {
                    throw new AssertionError("Unknown command: " + command);
                }
            } catch (Exception e) {
                System.out.println("ERROR:" + e.getClass().getSimpleName());
            }
            System.out.flush();
        }
    }
}
