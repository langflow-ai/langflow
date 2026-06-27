# Frontend E2E tests

Playwright end-to-end specs for the Langflow UI. Run with `make tests_frontend`
(see the root `AGENTS.md`).

## Reuse shared helpers — don't hand-roll setup

New specs MUST reuse the shared fixtures and helpers below instead of
re-implementing bootstrap, sidebar-drag, template, playground, or route-mock
blocks inline. This duplication is the single largest source of boilerplate in
the suite, so reviewers should flag any hand-rolled copy of a block a helper
already covers.

| Need | Use | Where |
| --- | --- | --- |
| Log in + land on the app | `awaitBootstrapTest(page)` | `utils/await-bootstrap-test.ts` |
| Open a starter-project template | `openStarterProject(page, name)` | `utils/flow/open-starter-project.ts` |
| Add a component from the sidebar | `addComponentFromSidebar(page, ...)` | `utils/flow/add-component-from-sidebar.ts` |
| Seed a flow via the API (no canvas) | `seedFlowViaApi(options)` fixture | `fixtures.ts` |
| Open a template + configure GPT | `seedGptTemplate(page, name)` | `utils/seed-gpt-template.ts` |
| Send a prompt + assert the reply | `runPlaygroundPrompt(page, { prompt, expect })` | `utils/playground/send-playground-message.ts` |
| Send a playground message (no assert) | `sendPlaygroundMessage(page, msg)` | `utils/playground/send-playground-message.ts` |
| Mock the deployment API routes | `setupDeploymentMocks(page, ...)` | `utils/deployment-mocks.ts` |

Prefer seeding state through `seedFlowViaApi` over rebuilding flows on the
canvas — UI rebuilds are the suite's main CI cost.

## Tags

Specs are tagged (`{ tag: [...] }`) so CI can filter which suites run. Do not
invent new tags or introduce typos (e.g. `@starter-projects`, never
`@starter-projectss`). The only allowed tags are:

`@release` · `@workspace` · `@api` · `@components` · `@starter-projects` ·
`@database`

**Every spec must carry `@release`** — it is the tag the release run greps for,
so an untagged or wrongly-tagged spec silently drops out of release coverage.
Add the domain tag(s) on top of `@release` (a spec can have more than one).
