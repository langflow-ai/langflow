---
name: frontend-i18n
description: Add, change, or review user-facing text in the Langflow frontend using the i18n system (i18next / react-i18next). Use whenever a change adds or edits UI strings — labels, buttons, tooltips, modals, toasts, error messages, empty states — or when reviewing a diff that contains user-facing text. Every user-facing string must go through the translation system and every new key must exist in ALL locale files. Do NOT use for backend strings, log messages, or code identifiers.
---

# Frontend i18n

The Langflow frontend is internationalized with **i18next + react-i18next**. Locales live in `src/frontend/src/locales/` — currently `en`, `de`, `es`, `fr`, `ja`, `pt`, `zh-Hans`. A hardcoded user-facing string, or a key missing from one locale, ships broken UI for part of the user base.

## The two rules

1. **Every user-facing string goes through `t(...)`** — never hardcoded JSX text for labels, buttons, tooltips, modals, toasts, errors, placeholders, `aria-label`s, or empty states.
2. **Every new key is added to ALL locale files in the same PR** (`en.json`, `de.json`, `es.json`, `fr.json`, `ja.json`, `pt.json`, `zh-Hans.json`). `fallbackLng: "en"` means a missing key silently shows English — it won't crash, which is exactly why reviews must catch it.

## How it works here

- Config: `src/frontend/src/i18n.ts` — a custom i18next instance. `en` is bundled statically; other languages are **lazy-loaded** by `loadLanguage()` via dynamic import. Language preference comes from `localStorage.getItem("languagePreference")`, normalized (e.g. `zh-CN` → `zh-Hans`, unknown → `en`).
- Keys are **flat, dot-namespaced by feature**: `deleteModal.title`, `errors.fileTooLarge`, `crash.restartButton`. Follow the existing namespace of the area you're touching; create a new prefix only for a genuinely new surface.
- Interpolation uses `{{variable}}` in the string and an options object in the call.

## Adding a string (the pattern)

```tsx
import { useTranslation } from "react-i18next";

const { t } = useTranslation();

<span>{t("deleteModal.title")}</span>
<p>{t("errors.fileTooLarge", { maxSizeMB: "10MB" })}</p>
```

In `locales/en.json` (and **every** other locale file):

```json
"errors.fileTooLarge": "The file size is too large. Please select a file smaller than {{maxSizeMB}}."
```

For the non-English locales, write a real translation when confident; if not, add the key with the English value and flag it in the PR — a present-but-untranslated key is visible and searchable, a missing key is invisible.

## Rules that prevent real bugs

- **Don't concatenate translated fragments** (`t("a") + name + t("b")`) — word order differs across languages. Use one key with interpolation: `t("greeting", { name })`.
- **Don't put JSX/HTML inside translation strings**; compose in JSX around `t()` calls (see how `crash.descriptionBefore` / `crash.githubIssues` / `crash.descriptionAfter` split around a link).
- **Plurals**: use i18next plural forms (`_one` / `_other` suffixes), not `count === 1 ? ... : ...`.
- **Keys are code**: renaming or deleting a key means updating **all seven** locale files — an orphan key in one file is dead weight; a rename missed in one file is a regression.
- Dates/numbers/currency: format with `Intl.*` using the active locale, never hardcoded formats.

## Review checklist (apply to any diff with UI text)

- [ ] No hardcoded user-facing string in JSX (including `placeholder`, `title`, `aria-label`, toast/error text).
- [ ] Every new key exists in **all** locale files (grep the key across `src/frontend/src/locales/*.json`).
- [ ] No concatenation of translated fragments; interpolation used instead.
- [ ] Removed/renamed keys cleaned up in all locales (no orphans).
- [ ] Key follows the existing dot-namespace of the feature area.

Quick check for a key across locales:

```bash
for f in src/frontend/src/locales/*.json; do grep -L '"my.new.key"' "$f"; done
```

(prints the locale files where the key is **missing** — should print nothing)
