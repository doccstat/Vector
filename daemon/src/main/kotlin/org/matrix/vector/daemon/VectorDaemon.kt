package org.matrix.vector.daemon

import android.app.ActivityManager
import android.app.ActivityThread
import android.content.Context
import android.ddm.DdmHandleAppName
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Parcel
import android.os.Process
import android.os.ServiceManager
import android.os.SystemProperties
import android.system.Os
import android.util.Log
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import org.matrix.vector.daemon.data.ConfigCache
import org.matrix.vector.daemon.data.FileSystem
import org.matrix.vector.daemon.env.CliSocketServer
import org.matrix.vector.daemon.env.CoreServiceGate
import org.matrix.vector.daemon.env.Dex2OatServer
import org.matrix.vector.daemon.env.LogcatMonitor
import org.matrix.vector.daemon.env.StartupLog
import org.matrix.vector.daemon.ipc.BRIDGE_TRANSACTION_CODE
import org.matrix.vector.daemon.ipc.ManagerService
import org.matrix.vector.daemon.ipc.SystemServerService
import org.matrix.vector.daemon.utils.applyNotificationWorkaround

private const val TAG = "VectorDaemon"
private const val ACTION_SEND_BINDER = 1

object VectorDaemon {
  private val exceptionHandler = CoroutineExceptionHandler { context, throwable ->
    Log.e(TAG, "Caught fatal coroutine exception in background task!", throwable)
  }

  // Dispatchers.IO: Uses the shared background thread pool.
  // SupervisorJob(): Ensures one failing task doesn't kill the whole daemon.
  val scope = CoroutineScope(Dispatchers.IO + SupervisorJob() + exceptionHandler)
  val bridgeServiceName = "activity"

  var isLateInject = false
  var proxyServiceName = "serial"

  private var startupLog: StartupLog? = null

  private fun startupPhase(phase: String) {
    runCatching { startupLog?.phase(phase) }
        .onFailure { Log.w(TAG, "Cannot write startup diagnostics", it) }
    Log.i(TAG, "Startup: $phase")
  }

  @JvmStatic
  fun main(args: Array<String>) {
    val acquired =
        try {
          FileSystem.tryLock()
        } catch (e: Exception) {
          Log.e(TAG, "Cannot acquire daemon lock; refusing to start", e)
          kotlin.system.exitProcess(1)
        }
    if (!acquired) {
      Log.i(TAG, "Another daemon owns the lock; skipping duplicate launch")
      kotlin.system.exitProcess(0)
    }

    // Only the lock owner rotates these files. They survive logcat initialization/rotation and
    // retain the stack Android deliberately suppresses when the cause is DeadSystemException.
    startupLog =
        runCatching { StartupLog.open(FileSystem.basePath) }
            .onFailure { Log.w(TAG, "Cannot open startup diagnostics", it) }
            .getOrNull()
    Thread.setDefaultUncaughtExceptionHandler { thread, error ->
      try {
        runCatching { startupLog?.failure(thread, error) }
        System.err.println("Vector: fatal on ${thread.name}: ${error.message}")
        Log.e(TAG, "Uncaught exception in Daemon on ${thread.name}", error)
      } finally {
        kotlin.system.exitProcess(1)
      }
    }
    startupPhase("locked; version ${BuildConfig.VERSION_CODE} commit ${BuildConfig.VERSION_HASH}")

    var systemServerMaxRetry = 1
    for (arg in args) {
      if (arg.startsWith("--system-server-max-retry=")) {
        systemServerMaxRetry = arg.substringAfter('=').toIntOrNull() ?: 1
      } else if (arg == "--late-inject") {
        isLateInject = true
        proxyServiceName = "serial_vector"
      }
    }

    Log.i(TAG, "Vector daemon started: lateInject=$isLateInject, proxy=$proxyServiceName")
    // The hash is here rather than in the version the manager prints: Home should stay readable,
    // but every saved bug report should say exactly which commit produced the daemon that wrote it.
    Log.i(
        TAG,
        "Version ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}) " +
            "commit ${BuildConfig.VERSION_HASH}")

    // Setup Main Looper
    startupPhase("prepare main looper")
    Process.setThreadPriority(Process.THREAD_PRIORITY_FOREGROUND)
    @Suppress("DEPRECATION") Looper.prepareMainLooper()

    // Squat on the proxy service name immediately, which creates the early IPC channel of
    // FrameworkService for our Zygisk module during system_server specialization.
    startupPhase("register early proxy $proxyServiceName")
    SystemServerService.registerProxyService(proxyServiceName)

    // Start Environmental Daemons
    startupPhase("start logcat monitor")
    LogcatMonitor.start()
    startupPhase("start environmental services")
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) Dex2OatServer.start()
    CliSocketServer.start()

    // Preload Framework DEX in the background
    scope.launch { FileSystem.getPreloadDex(ConfigCache.state.isDexObfuscateEnabled) }

    // ActivityThread initialization can call into system_server. Do not do it before the core
    // services exist, or accept dead cached Binders during a concurrent framework restart.
    // The specialization proxy stays early: it must not wait on system_server itself.
    awaitLiveCoreServices()
    startupPhase("initialize ActivityThread")
    // A Binder can still die after the readiness check. Do not retry partially initialized
    // ActivityThread state; the uncaught handler records the phase and full stack before exit.
    ActivityThread.systemMain()
    DdmHandleAppName.setAppName("org.matrix.vector.daemon", 0)

    startupPhase("notification workaround")
    applyNotificationWorkaround()

    // Read this before `sendToBridge`, which leaves the main thread at euid 1000: the config
    // database lives under a directory only root can enter, so the first process to open it has
    // to do so while we still have root. On a successful injection a binder thread opens it for
    // us during specialization, but when the injection fails nothing else has, and the daemon
    // used to die here on an unreadable preference.
    startupPhase("read preferences")
    val isVerboseLog = ManagerService.isVerboseLogEnabled()

    // Setup IPC channel for applications by injecting DaemonService binder
    startupPhase("inject application bridge")
    sendToBridge(VectorService.asBinder(), false, systemServerMaxRetry)

    if (!isVerboseLog) {
      LogcatMonitor.stopVerbose()
    }

    // This means the event loop is ready, not that the bridge injection succeeded.
    startupPhase("enter main loop")
    Looper.loop()
    throw RuntimeException("Main thread loop unexpectedly exited")
  }

  private fun awaitLiveCoreServices() {
    startupPhase("wait for live core services")
    CoreServiceGate.awaitReady(
        arrayOf("package", bridgeServiceName, Context.USER_SERVICE, Context.APP_OPS_SERVICE),
        { name ->
          val service = ServiceManager.getService(name)
          val alive = service?.pingBinder() == true
          if (service != null && !alive) clearSystemCaches()
          alive
        },
        { name ->
          Log.i(TAG, "Waiting system service: $name for 1s")
          Thread.sleep(1000)
        })
  }

  // The bridge is setup in `system_server` via Zygisk API
  @Suppress("DEPRECATION")
  private fun sendToBridge(
      binder: IBinder,
      isRestart: Boolean,
      restartRetry: Int,
  ) {
    check(Looper.myLooper() == Looper.getMainLooper()) {
      "sendToBridge MUST run on the main thread!"
    }

    Os.seteuid(0)

    runCatching {
          var bridgeService: IBinder?
          if (isRestart) Log.w(TAG, "system_server restarted...")

          while (true) {
            bridgeService = ServiceManager.getService(bridgeServiceName)
            if (bridgeService?.pingBinder() == true) break
            Log.i(TAG, "`$bridgeServiceName` service not ready, waiting 1s...")
            Thread.sleep(1000)
          }

          // Setup death recipient to handle system_server crashes
          val deathRecipient =
              object : IBinder.DeathRecipient {
                override fun binderDied() {
                  Log.w(TAG, "System Server died! Clearing caches and re-injecting...")
                  bridgeService.unlinkToDeath(this, 0)
                  clearSystemCaches()
                  SystemServerService.binderDied() // Cleanup old references
                  // Re-claim the service name immediately to ensure that when system_server
                  // restarts, our proxy is already there for the Zygisk module to find.
                  ServiceManager.addService(proxyServiceName, SystemServerService)
                  ManagerService.guard = null // Remove dead guard
                  Handler(Looper.getMainLooper()).post {
                    sendToBridge(binder, true, restartRetry - 1)
                  }
                }
              }
          bridgeService.linkToDeath(deathRecipient, 0)

          // Try sending the Binder payload (up to 3 times)
          var success = false
          for (i in 0 until 3) {
            val data = Parcel.obtain()
            val reply = Parcel.obtain()
            try {
              data.writeInt(ACTION_SEND_BINDER)
              data.writeStrongBinder(binder)
              success = bridgeService.transact(BRIDGE_TRANSACTION_CODE, data, reply, 0) == true
              reply.readException()
              if (success) break
            } finally {
              data.recycle()
              reply.recycle()
            }
            Log.w(TAG, "No response from bridge, retrying...")
            Thread.sleep(1000)
          }

          if (success) {
            Log.i(TAG, "Successfully injected Vector IPC binder for applications.")
          } else {
            Log.e(TAG, "Failed to inject VectorService into system_server")
            if (restartRetry > 0) restartSystemServer()
          }
        }
        .onFailure { Log.e(TAG, "Error during injecting DaemonService", it) }
    Os.seteuid(1000)
  }

  private fun clearSystemCaches() {
    Log.i(TAG, "Clearing ServiceManager and ActivityManager caches...")
    runCatching {
          // Clear ServiceManager.sServiceManager
          var field = ServiceManager::class.java.getDeclaredField("sServiceManager")
          field.isAccessible = true
          field.set(null, null)

          // Clear ServiceManager.sCache
          field = ServiceManager::class.java.getDeclaredField("sCache")
          field.isAccessible = true
          val sCache = field.get(null)
          if (sCache is MutableMap<*, *>) {
            sCache.clear()
          }

          // Clear ActivityManager.IActivityManagerSingleton
          field = ActivityManager::class.java.getDeclaredField("IActivityManagerSingleton")
          field.isAccessible = true
          val singleton = field.get(null)
          if (singleton != null) {
            val mInstanceField =
                Class.forName("android.util.Singleton").getDeclaredField("mInstance")
            mInstanceField.isAccessible = true
            synchronized(singleton) { mInstanceField.set(singleton, null) }
          }
        }
        .onFailure { Log.w(TAG, "Failed to clear system caches via reflection", it) }
  }

  /**
   * Brings the framework down and up without rebooting the device.
   *
   * `system_server` is forked from the *primary* zygote, so restarting that is what restarts the
   * framework — on a 64/32 device the primary init service is still called `zygote` (it runs
   * app_process64) and `zygote_secondary` is the 32-bit one. Restarting the secondary leaves
   * system_server running, which is right for [restartSystemServer]'s own purpose and wrong for
   * this one; they are separate functions for that reason.
   *
   * Everything on screen dies with it. The caller is expected to have said so first.
   */
  fun softReboot() {
    Log.w(TAG, "Soft reboot: restarting the primary zygote")
    SystemProperties.set("ctl.restart", "zygote")
  }

  fun restartSystemServer() {
    Log.w(TAG, "Restarting system_server...")
    val restartTarget =
        if (Build.SUPPORTED_64_BIT_ABIS.isNotEmpty() && Build.SUPPORTED_32_BIT_ABIS.isNotEmpty()) {
          "zygote_secondary"
        } else {
          "zygote"
        }
    SystemProperties.set("ctl.restart", restartTarget)
  }
}
