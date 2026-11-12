# Component compatibility release notes

Add a Markdown file here for each reviewed component contract break.
Include the component name, exact break identity from the CI comparison report, and the saved-flow migration action.
Reference that file from `scripts/ci/component_breaks.json`.
Copy `distribution`, `source_version`, and `target_version` from the break in the CI comparison report.
The gate includes the note when it runs that package and version comparison.
Keep the entry as release history when CI starts comparing against a newer published version.
Do not add an acknowledgment for an unreviewed or accidental regression.
