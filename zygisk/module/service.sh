# Extract the directory path and change directory 
MODDIR="${0%/*}"
cd "$MODDIR" || exit 1

# `/system/bin/unshare` is toybox and rejects `--propagation`, which aborted
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

# Start the daemon directly in the background within a private mount namespace
unshare --propagation slave -m "$MODDIR/daemon" --system-server-max-retry=3 "$@" &
