#!/system/bin/sh
# VECTOR_SERVICE_V2: the daemon's FileSystem.tryLock() owns the singleton.
MODDIR="${0%/*}"
cd "$MODDIR" || exit 1
MODDIR="$PWD"

# This is only a fast path. Concurrent launches are serialized by the daemon's
# kernel file lock, which is released on process death and reboot.
if pidof vectord >/dev/null 2>&1; then
    exit 0
fi

# Set propagation inside the new namespace, before the daemon mounts anything.
# Both toybox and busybox accept -m; toybox has no --propagation option.
unshare -m sh -c 'mount --make-rslave / && exec "$@"' vector-namespace \
    "$MODDIR/daemon" --system-server-max-retry=3 "$@" &
