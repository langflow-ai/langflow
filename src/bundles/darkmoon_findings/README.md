# lfx-darkmoon-findings

Darkmoon findings parser component as a standalone Langflow Extension Bundle.

[Darkmoon](https://github.com/ASCIT31/Dark-Moon) is an open source (GPL-3.0)
autonomous AI penetration testing platform. A scan writes its findings as JSON.
The bundle ships a single component, `DarkmoonFindingsParserComponent`, that
reads that JSON, filters it by severity and proof status, sorts it most severe
first, summarizes it, and can flag a severity gate for a flow that should stop
on a serious finding.

The component is pure computation over a findings file you already have. It
makes no network calls, calls no Darkmoon service, and needs no credentials or
API key.

## Install

```bash
pip install lfx-darkmoon-findings
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the
`DarkmoonFindingsParserComponent` will appear in the palette's **Bundles**
section under **Darkmoon Findings**.

## Configure

Connect the findings JSON of a Darkmoon scan to the **Findings** input, as
JSON text, a **Message**, a **JSON** object, or a **Table**. A bare array of
findings, or an object with a `findings` or `data` array, is accepted.
**Minimum Severity**, **Proof Status**, and **Fail On Severity** are optional.

The component has three outputs: a findings table, a summary (`total`,
`severity_counts`, `highest_severity`, `gate_failed`), and a Markdown report.

## Develop

```bash
cd src/bundles/darkmoon_findings
pip install -e .
lfx extension validate src/lfx_darkmoon_findings
```

## Manifest

The extension manifest is shipped at `src/lfx_darkmoon_findings/extension.json`
and points at the bundle at `components/darkmoon_findings`. The component
registers under the canonical namespaced ID
`ext:darkmoon_findings:DarkmoonFindingsParserComponent@official`.
