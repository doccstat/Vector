package org.matrix.vector.daemon.env;

import java.util.function.Predicate;

/** A point-in-time readiness gate, not a guarantee against later framework death. */
public final class CoreServiceGate {
    private CoreServiceGate() {}

    @FunctionalInterface
    public interface Waiter {
        void await(String missingService) throws InterruptedException;
    }

    /**
     * Recheck the whole set after each wait. Sequential per-service waits can accept a service
     * from the old system_server and another from its replacement. The predicate must test a
     * live Binder, not just whether servicemanager returned a non-null cached reference.
     *
     * This never initializes the framework, relaunches the daemon, or restarts Android. Failures
     * other than an unavailable service propagate to the caller's startup diagnostics.
     */
    public static void awaitReady(String[] services, Predicate<String> isAlive, Waiter waiter)
            throws InterruptedException {
        while (true) {
            String missing = null;
            for (String name : services) {
                if (!isAlive.test(name)) {
                    missing = name;
                    break;
                }
            }
            if (missing == null) return;
            waiter.await(missing);
        }
    }
}
