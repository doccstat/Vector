package org.matrix.vector.daemon.env;

import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.FileAttribute;
import java.nio.file.attribute.PosixFilePermissions;
import java.time.Instant;
import java.util.Arrays;
import java.util.HashSet;

/**
 * Synchronous, bounded diagnostics independent of logd and Android's Throwable filtering.
 * Open only AFTER acquiring the daemon lock: a duplicate launch must not rotate the owner's log.
 * The parent directory must already be private to root. Keep this outside log/log.old, which the
 * asynchronous logcat monitor rotates during its own initialization.
 */
public final class StartupLog implements AutoCloseable {
    private static final int MAX_BYTES = 128 * 1024;
    private final FileChannel channel;
    private int written;
    private String phase = "acquired daemon lock";

    private StartupLog(FileChannel channel) {
        this.channel = channel;
    }

    public static StartupLog open(Path directory) throws IOException {
        Path current = directory.resolve("startup.log");
        if (Files.exists(current, LinkOption.NOFOLLOW_LINKS)) {
            if (!Files.isRegularFile(current, LinkOption.NOFOLLOW_LINKS)) {
                throw new IOException("Refusing non-regular startup log: " + current);
            }
            Files.move(current, directory.resolve("startup.log.old"),
                    StandardCopyOption.REPLACE_EXISTING);
        }
        FileAttribute<?>[] attributes = {
            PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------"))
        };
        // CREATE_NEW checks existence atomically and rejects even dangling symlinks.
        return new StartupLog(FileChannel.open(current,
                new HashSet<>(Arrays.asList(StandardOpenOption.CREATE_NEW,
                        StandardOpenOption.WRITE)), attributes));
    }

    public synchronized void phase(String phase) throws IOException {
        this.phase = phase;
        // Leave half the budget for a fatal stack even if a future caller adds many phases.
        if (written < MAX_BYTES / 2) append("Phase: " + phase + "\n", MAX_BYTES / 2);
    }

    public synchronized void failure(Thread thread, Throwable error) throws IOException {
        StringWriter stack = new StringWriter();
        error.printStackTrace(new PrintWriter(stack));
        append("Fatal on " + thread.getName() + " during " + phase + "\n" + stack, MAX_BYTES);
    }

    private void append(String text, int limit) throws IOException {
        byte[] bytes = (Instant.now() + " " + text).getBytes(StandardCharsets.UTF_8);
        int remaining = limit - written;
        if (remaining <= 0) return;
        byte[] marker = "\n[diagnostic truncated]\n".getBytes(StandardCharsets.UTF_8);
        boolean truncated = bytes.length > remaining;
        int length = truncated ? Math.max(0, remaining - marker.length) : bytes.length;
        write(ByteBuffer.wrap(bytes, 0, length));
        if (truncated) write(ByteBuffer.wrap(marker, 0, Math.min(marker.length, remaining - length)));
        channel.force(false);
    }

    private void write(ByteBuffer buffer) throws IOException {
        while (buffer.hasRemaining()) written += channel.write(buffer);
    }

    @Override
    public synchronized void close() throws IOException {
        channel.close();
    }
}
