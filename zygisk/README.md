# Vector Zygisk Module and Framework Loader

## Overview

This subsystem constitutes the injection engine of the Vector framework. It acts as the bridge between the Android Zygote process and the high-level Java/Kotlin Xposed API. The architecture is designed to avoid standard Android service registration and disk-based class loading, operating entirely through in-memory execution, JNI-level Binder interception, and process identity transplantation.

The subsystem is divided into two discrete layers:
1. _Native Zygisk Layer_ (C++): Hooks process creation via Zygisk, filters target processes, establishes the initial IPC bridge, and bootstraps the Dalvik environment from memory.
2. _Framework Loader_ (Kotlin): The Java-world payload. It handles high-level Android framework manipulation, manages the custom Binder routing service, and orchestrates the Parasitic Manager execution.

## Daemon launch lifecycle

The package owns this lifecycle; no companion rooting app or device-specific
compatibility script is involved. `module/customize.sh` extracts verified
payloads and explicitly labels the module tree `system_file` (dex2oat wrappers
retain `xposed_file`), rather than assuming a root manager's default label. The
daemon also reasserts the manager APK label if a platform relabel changed it.

`module/service.sh` creates an isolated mount namespace and makes it recursively
slave before `module/daemon` mounts its resource cache. It explicitly runs
Android's `/system/bin/mount -t rootfs -o rslave rootfs /` inside the namespace:
two operands avoid Toybox's fstab lookup, and an explicit type prevents automatic
bind mounting. The kernel ignores source/type for this propagation-only operation.
Do not replace it with BusyBox's `--make-rslave /` or Toybox's `-o rslave / /`;
the latter can succeed as a bind mount without establishing isolation.

Namespace or mount failure stops the launch; it must never fall back to mounting
in the caller's namespace. Failed asynchronous launches are reported to stderr
and the `Vector` logcat tag.

The daemon's `DaemonLock` is the sole singleton authority. Its open kernel file
lock survives framework restarts and is released on process death, SIGKILL, or
reboot. A leftover lock file is harmless and must not be deleted; unlinking it
could allow two owners to lock different inodes. Process names and historical
`.vectord-start` directories are not ownership checks. Only actual contention
is a successful duplicate no-op; lock I/O errors are logged and exit nonzero.
There is no automatic launcher retry/reboot loop.

Enabled module metadata or a library held by Zygisk proves neither daemon health
nor successful framework injection. Check `Vector`/`VectorDaemon` logcat output
and the daemon process separately before considering a restart.

Host regression tests (Linux, Python 3, JDK 21, `unzip`, `toybox`, `busybox`,
`strace`, standard shell utilities including `sha256sum`; run **unprivileged**
from the project root):

```sh
python3 -m unittest discover -s daemon/tests -v
python3 -m unittest discover -s zygisk/tests -v
```

The lock tests compile the production Java class and use separate JVMs, including
concurrent contenders and SIGKILL recovery. Launcher tests mock namespace/mount
commands and never mount anything on the host. The standalone installation tests
execute `customize.sh` → `service.sh` → `daemon` without any companion package,
using Magisk/KernelSU/APatch-style installer environments and all four ABIs. They
cover checksum rejection, explicit labels, file modes, release/debug VM options,
and argument preservation. ZIP extraction and checksums are real; root-manager
helpers, SELinux operations, namespaces, mounts and `app_process` are simulated.
Mount-parser tests additionally execute real Toybox and BusyBox through `strace`
syscall injection: every `mount()` is suppressed, but its parsed flags must
contain `MS_SLAVE|MS_REC`, not `MS_BIND`. These tests refuse root and catch
false-success argument forms that a shell mock cannot. Override tool paths with
`VECTOR_TEST_TOYBOX`, `VECTOR_TEST_BUSYBOX` and `VECTOR_TEST_STRACE` if needed.
Missing tools or unavailable ptrace/syscall injection fail the suite, not skip it.

These tests run before CI packaging, not instead of it. Actual root-manager
integration, Android/ART execution and physical-device startup remain separate
validation gates; the host matrix does not certify every ROM or device.

## IPC Architecture and Binder Relay

Vector utilizes a two-phase IPC routing mechanism to establish communication between injected applications and the root daemon. Instead of registering standard AIDL endpoints with ServiceManager, it intercepts the lowest level of Java Binder communication within the Dalvik VM.

### The JNI Binder Trap
In `ipc_bridge.cpp`, the module uses the ART internal function `SetTableOverride` to replace the JNI function `CallBooleanMethodV`. This override intercepts all native calls to `android.os.Binder.execTransact` system-wide. 

When a transaction occurs, the hook inspects the transaction code. If it matches the constant kBridgeTransactionCode (`_VEC`), the transaction is diverted to the static Kotlin method `BridgeService.execTransact`. All other transactions pass through to the original Android framework unmodified.

### Phase 1: System Server Initialization
The `system_server` acts as the primary proxy router for the framework. During the `postServerSpecialize` callback, the following sequence occurs:
1. The native module queries `ServiceManager` for the `serial` service (or `serial_vector` for late-inject scenarios). This service acts as a temporary rendezvous point.
2. The module sends a `_VEC` transaction to retrieve a temporary binder, which it uses to fetch the framework DEX file descriptor and the obfuscation map.
3. The module installs the JNI Binder Trap (`HookBridge`) and bootstraps the Kotlin layer via `Main.forkCommon`.
4. Concurrently, the root daemon initiates a Binder transaction directly to the `system_server`. The JNI trap intercepts this, and BridgeService processes the `SEND_BINDER` action, storing the daemon's primary `IVectorDaemon` binder, sending back `system_server` context and linking a `DeathRecipient`.

### Phase 2: User Application Rendezvous
Standard applications initialize their IPC connection by routing requests through the `system_server`.
1. In `postAppSpecialize`, the application queries `ServiceManager` for the `activity` service (which resides in `system_server`).
2. The application sends a `_VEC` transaction containing the `GET_BINDER` action, its process name, and a newly allocated heartbeat `BBinder`.
3. The JNI trap inside `system_server` intercepts this transaction before the Activity Manager processes it.
4. The `system_server`'s BridgeService forwards the application's UID, PID, and heartbeat binder to the root daemon via the `IVectorDaemon` binder acquired in Phase 1.
5. The daemon evaluates the request against its internal scope state. If approved, it generates an `IFrameworkService` binder and returns it to the `system_server`, which writes it back to the waiting application's reply parcel.
6. The application uses this dedicated binder to fetch its specific framework DEX and obfuscation map.

### The Heartbeat Mechanism
To manage process lifecycles without polling, the native module generates a dummy Binder object (`heartbeat_binder`) during both initialization phases. This object is passed to the daemon and kept alive in the application process via a JNI Global Reference (`env->NewGlobalRef`). If the application or `system_server` terminates normally or is killed by the kernel, the global reference is destroyed, the binder node is released, and the daemon's `DeathRecipient` triggers immediate resource cleanup.

## Memory Execution and Obfuscation Synchronization

Vector does not write framework code to the /data partition.

1. Asset Delivery: The root daemon provides the framework DEX via a `SharedMemory` file descriptor, using `kDexTransactionCode`. The C++ layer wraps this file descriptor in a `java.nio.DirectByteBuffer` and initializes a `dalvik.system.InMemoryDexClassLoader`.
2. Dynamic Relinking: The daemon randomizes framework class names on each boot. The native module fetches a serialized dictionary over IPC, using `kObfuscationMapTransactionCode`. `SetupEntryClass` uses this map to locate the randomized entry point (`org.matrix.vector.core.Main`) and BridgeService, enabling the framework to link correctly at runtime.

## Parasitic Manager and Identity Transplantation

The Vector Manager application is not installed as a standard package. It runs by hollowing out a host process (e.g., `com.android.shell`) using a parasitic execution model.

### System Server Intent Redirection
Within the `system_server`, `ParasiticManagerSystemHooker` intercepts `ActivityTaskSupervisor.resolveActivity`. When it detects an Intent tagged with the `LAUNCH_MANAGER` category, it dynamically modifies the returned ActivityInfo. It forces the system to launch the host package while setting the processName to the Manager's package name and adjusting theme and recents flags to mimic a standalone application.

### Application Host Hijacking
When the native module detects the host package UID and the Manager process name during `preAppSpecialize`, it injects `GID_INET` (3003) into the process's GID array to ensure network access. Control is then passed to `ParasiticManagerHooker.kt`, which performs the identity transplantation:
1. Code Injection: It intercepts `LoadedApk.getClassLoader` and `ActivityThread.handleBindApplication`, swapping the host's ApplicationInfo with a hybrid object constructed from the manager's APK (provided via file descriptor). The manager's DEX is injected into the host's `PathClassLoader`.
2. State Forgery: The system ActivityManager is unaware of the spoofed Manager activities. To prevent data loss during lifecycle transitions (e.g., screen rotation), the hooker intercepts `performStopActivityInner` to manually capture Bundle and PersistableBundle states into static concurrent maps. These states are reinjected during `scheduleLaunchActivity`.
3. Context Spoofing: It intercepts `ActivityThread.installProvider` and `WebViewFactory.getProvider` to construct forged `ContextImpl` instances, bypassing internal Android and Chromium package-name validation checks.
