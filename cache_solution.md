# Langflow Cache Normalization and Envelope Strategy

This document outlines a robust, back-end-agnostic caching strategy for Langflow that supports dynamic user components while keeping distributed caches reliable and portable.

## Design Goals

- Support arbitrary user-defined components (dynamic code, runtime registration).
- Ensure cache backends (memory, disk, Redis, future backends) can store and retrieve values safely.
- Do not store executable objects in distributed caches; store data/description/references only.
- Version and fingerprint cache entries to enable safe evolution and automatic invalidation.

## Core Principles

- Boundary normalization: before writing to any cache backend, convert values to normalized DTOs comprised of JSON-friendly primitives and small descriptors.
- Rebuild-avoidance: cache stores data/description/references rather than executable Python objects.
- Component policy: components can declare their cache policy (e.g., result only, artifacts by ref, disabled).
- Content-addressability: cache keys include input signature and component code hash/version to avoid stale entries.

## What Gets Normalized

Normalization converts complex runtime objects to a stable representation:

- Classes → `{"__class_path__": "module.Class"}`
- Functions/methods → `{"__callable_path__": "module.qualname"}`
- Pydantic models → `.model_dump()`
- Dynamic/custom component instances (e.g., `lfx.custom.*`, `<locals>`, `__main__`) → `{"__repr__": "..."}`
- Generators/iterators → `{"__non_cacheable__": "generator"}`
- Large artifacts → external storage refs (e.g., `{"__artifact_ref__": "cas://sha256:..."}`) [future]
- Vertex snapshots → normalized dict with a placeholder for `built_object` to avoid executable state in cache. A marker `"__cache_vertex__": true` is added.

Containers are handled recursively with cycle protection. Unknown complex objects fall back to a repr descriptor.

## Envelope (Optional)

We keep compatibility with current cache layout by storing normalized data in the existing `{"result": <normalized>, "type": "normalized"}` shape. The design supports an optional versioned envelope if/when needed:

```json
{
  "__envelope_version__": 1,
  "result": { ... normalized value ... },
  "type": "normalized",
  "meta": { "component": "repr or class path", "policy": "RESULT_ONLY" }
}
```

## Backend Compatibility

- InMemory / AsyncInMemory: store normalized dicts directly, no change required.
- Disk (diskcache + pickle): stores normalized dicts (primitive structures); fully compatible.
- Redis: stores normalized dicts without executable objects; no dill recursion warnings.
- Future backends: any storage that accepts bytes/JSON will work with normalized DTOs.

## Integration Points

- Normalizer implemented at `lfx.serialization.normalizer.normalize_for_cache`.
- `ChatService.set_cache` now normalizes data before writing to any cache.
- Graph cache restore supports normalized vertex snapshots: if `"built_object"` contains a placeholder, the runtime reconstructs a safe value for execution (`UnbuiltObject`).

## Testing

- Unit tests validate normalization of dynamic classes/functions, Pydantic models, and vertex snapshots.
- ChatService caching tests verify that stored values are normalized and retrievable without backend-specific assumptions.

## Migration Strategy

- Apply normalization in upper layers (service/graph) so backends remain dumb stores.
- Keep Redis’s defensive serialization as a belt-and-suspenders approach for a time window.
- Evolve toward a stricter JSON/MsgPack format if desired; the normalizer provides the required invariants.

