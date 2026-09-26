<div align="center">

# libxposed API (API 102)

**The Modern, Type-Safe, High-Performance ART Hooking Specification for Android**

[![API](https://img.shields.io/badge/API-102-brightgreen.svg?style=flat-square)](https://github.com/Ahmoze/libxposed-api)
[![Javadoc](https://img.shields.io/badge/Javadoc-API%20102%20Online-blue.svg?style=flat-square)](https://ahmoze.github.io/libxposed-api/)
[![Android](https://img.shields.io/badge/Android-8.1%20~%2017-orange.svg?style=flat-square)](https://developer.android.com)
[![minSdk](https://img.shields.io/badge/minSdk-26-yellow.svg?style=flat-square)](https://developer.android.com/about/versions/oreo)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square)](LICENSE)

</div>

---

### Overview

**libxposed API** is the next-generation, type-safe, and process-isolated replacement for the legacy `XposedBridge` API. Originally architected by the LSPosed team and continued under the Vector project, it provides standard hooking interfaces for modern Android runtimes without requiring root-level zygote injection.

This repository serves as the official mirror and active maintenance home for **API 102**, providing live interactive Javadoc documentation and source definitions.

---

### ✨ What's New in API 102

Compared to the baseline API 101, **API 102** introduces major enhancements for modern module development:

* **🔥 Dynamic Hot Reloading:**
  * Introduces `onHotReloading(HotReloadingParam)` and `onHotReloaded(HotReloadedParam)` in `XposedModuleInterface`.
  * Allows module developers to dynamically push code updates into target running processes without restarting the app or rebooting Android.
* **🔓 Lifecycle Detachment (`detach()`):**
  * Modules can stop receiving subsequent lifecycle callbacks dynamically via `XposedInterfaceWrapper#detach()`.
* **🛡️ Classloader Isolation & Leak Prevention:**
  * Implements strict classloader checks to prevent stale objects created by previous module classloaders from persisting across hot reload cycles.
* **⚡ Modern Android 15, 16 & 17 Support:**
  * Fully adapted for modern ART runtime restrictions, eliminating hidden API exemptions that crash on Android 16 (API 36) release builds.

---

### 📖 API Version History

| API Level | Release Version | Key Features & Architectural Changes |
| :---: | :---: | :--- |
| **102** | `102.0.0` | **Hot Reloading**, `detach()` lifecycle support, strict classloader lifecycle management, Android 16 & 17 runtime compatibility. |
| **101** | `101.0.1` | Initial type-safe API release. Scope-based process loading (no zygote injection), modernized `Hooker` and `Invoker` interfaces. |

---

### 💻 Integration

#### For Module Developers

Add the API dependency to your module's `build.gradle.kts`:

```kotlin
dependencies {
    // Compile against the modern libxposed API 102
    compileOnly("io.github.libxposed:api:102.0.0")
}
```

*Or for Groovy (`build.gradle`):*

```groovy
dependencies {
    compileOnly 'io.github.libxposed:api:102.0.0'
}
```

#### For Framework Developers (Hooking Engines)

```kotlin
dependencies {
    implementation("io.github.libxposed:api:102.0.0")
}
```

---

### 📚 Documentation & Resources

* 🌐 **[Interactive Javadoc (API 102 Reference)](https://ahmoze.github.io/libxposed-api/):** Full online browsing of all classes, interfaces, and methods.
* 🚀 **[Vector-X Framework](https://github.com/Ahmoze/Vector-X):** Production ART hooking framework implementing libxposed API 102.
* ⚙️ **[libxposed-service](https://github.com/Ahmoze/libxposed-service):** Inter-process service bridge for framework-to-manager communications.
* 📘 **[Legacy Xposed Wiki](https://github.com/LSPosed/LSPosed/wiki/Develop-Xposed-Modules-Using-Modern-Xposed-API):** Conceptual guide to transitioning from legacy XposedBridge to modern libxposed.

---

### 📄 License

```
Copyright (C) 2023-2026 libxposed contributors
Copyright (C) 2026 Ahmoze

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
```
