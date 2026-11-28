# Lazy service factory fallbacks

`ServiceManager.get(name, default=instance)` remains supported. A caller can
instead pass `default_factory=FactoryClass` or another zero-argument provider.
The manager invokes that provider only when the service is absent and discovery
finds neither a service class nor a registered factory. A supplied `default`
instance takes precedence over the provider. Settings keep their built-in
factory path. Backend dependency getters now pass factory classes.

Resolution stays under the requested service's existing keyed lock. Warm
lookups return the managed instance without constructing a fallback, running
fallback dependency inference, or using a second service cache. Registered
factories still own recreation; teardown clears the registries, so a later
lookup resolves a fresh fallback. Plugin discovery and direct-class precedence
are unchanged.

Factory-constructor side effects and failures move from every helper lookup to
actual fallback creation. An unused fallback constructor can no longer reject
a warm or plugin-provided lookup. A failing provider publishes neither a factory
nor a service; the next lookup may retry. Existing dependency creation and
service readiness behavior remain unchanged.

This does not repair the existing cross-root dependency race: different root
lookups can still create the same uninitialized dependency concurrently. A
synchronized experiment with real state/tracing factories reproduced two
settings instances on both base and head; sequential controls shared one.
Same-root concurrent fallback resolution is covered by a deterministic test.

The helper benchmark is `scripts/benchmark/service_factory_lookup.py`. It
reports constructor/inference counts, timings, and traced memory separately.
Its enlarged type maps use aliases and do not represent more initialized
production services. The authenticated ASGI regression test can emit longer
interleaved measurements with `LANGFLOW_FACTORY_BENCHMARK_PAIRS=20` and pytest
`-s`. It compares normalized responses with authentication, native tracing,
and SQLite persistence enabled. Timings are observations, not test thresholds
or production latency guarantees. No schema migration or new setting is needed.
