#!/system/bin/sh
# VECTOR_SERVICE_V2: the daemon's FileSystem.tryLock() owns the singleton.
MODDIR="${0%/*}"
cd "$MODDIR" || exit 1
MODDIR="$PWD"

# Always let the daemon acquire its kernel lock. A process name, PID file, or
# directory is not proof of ownership, and must not suppress a future launch.
# Set propagation inside the new namespace, before the daemon mounts anything.
# Both toybox and busybox accept -m; toybox has no --propagation option.
(
    unshare -m sh -c 'mount --make-rslave / && exec "$@"' vector-namespace \
        "$MODDIR/daemon" --system-server-max-retry=3 "$@"
    status=$?
    if [ "$status" -ne 0 ]; then
        message="Daemon launch failed (exit $status); check namespace/mount errors and VectorDaemon logs"
        echo "Vector: $message" >&2
        log -p e -t Vector "$message"
    fi
) </dev/null &
