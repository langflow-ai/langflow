// Lothal product version — the single source of truth for the version badge
// shown across the lothal surface (Dashboard TopBar, Workspace TopBar, landing
// footer). This is a Lothal-surface concern, deliberately separate from the
// monorepo's Python/npm versions, which track upstream Langflow (1.9.5).
//
// The value is injected at BUILD TIME from the `LOTHAL_VERSION` env var (wired
// through vite.config.mts → `import.meta.env.LOTHAL_VERSION`). We version by
// epic: the build shipped after Epic X closes is `v0.X`. The deploy that builds
// the image passes the version (deploy-lothal.yml `version` input → frontend
// Docker build-arg), so the badge and the GHCR image tag always agree and there
// is no hardcoded number to bump.
//
// Default "dev": any build that doesn't stamp a version (local `make frontend`,
// un-tagged container builds, jest) shows "vdev" — an honest "not a release".
export const LOTHAL_VERSION = import.meta.env.LOTHAL_VERSION || "dev";
