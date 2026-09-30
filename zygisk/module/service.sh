# Extract the directory path and change directory 
MODDIR="${0%/*}"
cd "$MODDIR" || exit 1

# RMP_VECTOR_UNSHARE: `/system/bin/unshare` is toybox and rejects `--propagation`, which aborted
# this script before `vectord` ever started. KernelSU's (and Magisk's) busybox
# does support it, so shadow the external command for this script only and let
# the plain `unshare` call below pick the capable build.
unshare() {
    for _vector_busybox in /data/adb/ksu/bin/busybox /data/adb/magisk/busybox; do
        if [ -x "$_vector_busybox" ]; then
            "$_vector_busybox" unshare "$@"
            return $?
        fi
    done
    command unshare "$@"
}

# Start the daemon directly in the background within a private mount namespace.
# KernelSU replays service scripts during a userspace soft reboot.  The old
# daemon normally survives that restart, so do not start a second one.  The
# RMP_VECTOR_SINGLETON: do not replay an existing vectord.  mkdir is an atomic
# cross-process guard for the small window before the first daemon is visible
# to pidof.
if pidof vectord >/dev/null 2>&1; then
    exit 0
fi

_VECTOR_START_LOCK=/data/adb/lspd/.vectord-start
if ! mkdir "$_VECTOR_START_LOCK" 2>/dev/null; then
    exit 0
fi

(
    trap 'rmdir "$_VECTOR_START_LOCK" 2>/dev/null' EXIT
    if pidof vectord >/dev/null 2>&1; then
        exit 0
    fi
    # Keep the lock for the lifetime of the daemon.  If it exits before its
    # name is registered, the trap still releases the lock for a later retry.
    unshare --propagation slave -m "$MODDIR/daemon" --system-server-max-retry=3 "$@"
) &
