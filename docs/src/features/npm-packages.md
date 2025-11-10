# NPM Package Workflow (Chat Widget Example)

## Overview

This note documents what has been built: a first npm package drawn from the Langflow repo,
along with the tooling required to publish it.
Package name: `@langflow/chat-widget`, a React wrapper around our `<langflow-chat>` web component.
It can be dropped into any external site (e-commerce support portal, internal knowledge base, etc.)
to surface Langflow-powered conversations. Future candidates will follow the same template, but
for now this page is only summarising the current setup and the experiments still underway.

The sections below record:

- the structure of the package that lives in `src/frontend/chat-widget`
- how the build toolchain is configured
- how to publish the package to a registry
- how to identify additional components that could graduate into their own packages

## Repository Layout

```
src/frontend/chat-widget/
├── README.md            # consumer-facing usage guide
├── package.json         # npm package metadata and scripts
├── project.json         # Vite build task (kept minimal)
├── tsconfig.json        # overrides root TS settings (composite + emit)
├── tsconfig.lib.json    # lib build options (outDir, include/exclude)
├── vite.config.ts       # bundler configuration for library mode
└── src/
    ├── LangflowChat.tsx        # thin React wrapper loading the web component
    ├── index.ts                # re-exports for consumers
    ├── langflow-chat.d.ts      # JSX + attribute typings for `<langflow-chat>`
    └── types.ts                # strongly typed props accepted by the wrapper
```

Important differences from the main frontend:

- `tsconfig.json` sets `"composite": true` and overrides `"noEmit": false` so TypeScript
  will emit declaration files when the library builds. The file still extends the
  root config for linting and strictness.
- `tsconfig.lib.json` writes output to `../dist/chat-widget`; the root tools ignore this directory.
- `vite.config.ts` runs Vite in “library mode” (ESM + CJS bundles, external React peer deps).

## Build & Test Commands

From `src/frontend/chat-widget/`:

- `npm run build` – runs the Vite library build defined in `project.json`
- `npm pack` – (optional) produces a tarball you can test install locally

Because the wrapper is intentionally thin, unit tests aren’t required yet; if you add logic, add
React Testing Library tests alongside the components.

## Publishing to a Registry

1. Build the package: `npm run build`
2. Bump the version in `package.json`
3. (Optional) Inspect the tarball: `npm pack`
4. Publish to your registry (Verdaccio, npm, GitHub Packages, etc.)

Example (Verdaccio running locally):
```bash
npm login --registry http://localhost:4873
npm publish --registry http://localhost:4873
```

Consumers can then install the package exactly as documented in `README.md`.

## Example Use Cases

- **E-commerce support widget**
  Embed the chat widget into a product catalogue to answer inventory questions,
  track orders, or search documents. Pair with an OpenRAG flow that indexes SKUs
  or FAQ entries so the agent can respond in real time.

- **Internal knowledge base**
  Place the widget on an intranet page to surface HR policies or engineering runbooks.
  Leverage the same package; only the Langflow backend flow and credentials change.

- **SaaS customer onboarding**
  Offer guided walkthroughs or troubleshooting assistance inside a dashboard.
  Customize the widget props (title, styles) while reusing the shared package.

These scenarios follow the same pattern: host a Langflow backend, expose an API key,
and configure the chat widget props (host URL, flow ID, chat styling) in the consuming app.

We are still exploring which other Langflow components could ship the same way.
Candidates include reusable flow output visualisations, a lightweight API client SDK,
or UI for selecting starter flows. For now the focus is on validating the chat widget
in real integrations.

## Feature Flags (Optional)

All configurable feature flags live in `src/lfx/src/lfx/services/settings/feature_flags.py`.
The chat widget package is guarded by `chat_widget_package: bool = False`, which maps to the
environment variable `LANGFLOW_FEATURE_CHAT_WIDGET_PACKAGE`. Flip it to `true` in any environment
where the npm package should be surfaced; leave it `false` to avoid exposing the new integration in
the next deployment.

For additional flags, add a boolean to `FeatureFlags` and check it in the React app
via `useUtilityStore((state) => state.featureFlags)`.
Enable it per environment with an env var such as `LANGFLOW_FEATURE_CHAT_WIDGET_PREVIEW=true`.

## Checklist for New Packages

- [ ] Housed under `src/frontend/<package-name>/`
- [ ] `README.md` documents install and usage
- [ ] `package.json` has correct `"name"`, `"version"`, `"peerDependencies"`
- [ ] `tsconfig.json` has `"composite": true`, `"noEmit": false`
- [ ] `vite.config.ts` exports both ESM and CJS builds (React as peer dependency)
- [ ] Optional flag wiring documented if the main app needs to hide new features

## Further Exploration

Potential future packages:

- **Flow output renderers** – shared visualizations for traces, logs, or component outputs.
- **Auth helpers** – a minimal SDK for generating Langflow API requests from third-party apps.
- **Template pickers** – reusable UI for listing and launching Langflow starter flows.

When evaluating candidates, confirm the component:

1. Has a clear, external-facing API surface (props, events, or functions).
2. Can rely on generic HTTP APIs rather than direct Zustand stores.
3. Adds value outside the Langflow app itself (e.g. embedding, dashboards, integrations).

Following this checklist keeps the npm ecosystem lightweight and targeted at real integration needs.

Follow the chat widget’s pattern and you can scale the npm ecosystem without re-introducing the Nx
tooling we removed during the rebase.


