package org.matrix.vector.daemon.data;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.EnumSet;

/**
 * A process-lifetime singleton lock. Keep one instance per path in each process.
 *
 * <p>The file's existence is not ownership. Never unlink it: another process could then lock a
 * different inode while the original owner is still alive. The kernel releases ownership even on
 * SIGKILL or reboot, without an exit trap, PID file, or stale-directory cleanup.
 */
public final class DaemonLock {
    private final Path path;
    // FileLock retains its channel; both must stay open for the lifetime of the daemon.
    private FileLock lock;

    public DaemonLock(Path path) {
        this.path = path;
    }

    /**
     * Returns false only when another process owns the lock. I/O errors must reach the caller rather
     * than masquerade as a healthy running daemon. A repeated call by this owner does not reopen the
     * file: closing any descriptor for it can release this process's POSIX locks.
     */
    public synchronized boolean tryAcquire() throws IOException {
        if (lock != null && lock.isValid()) return true;

        FileChannel channel = FileChannel.open(
                path,
                EnumSet.of(StandardOpenOption.CREATE, StandardOpenOption.WRITE),
                PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")));
        boolean acquired = false;
        try {
            FileLock candidate = channel.tryLock();
            if (candidate == null) return false;
            lock = candidate;
            acquired = true;
            return true;
        } finally {
            if (!acquired) channel.close();
        }
    }
}
