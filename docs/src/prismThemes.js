// Prism syntax highlighting themes for code blocks (see docusaurus.config.js).
// All colors pass WCAG AA (4.5:1) against their backgrounds — validated with
// the IBM Equal Access checker (see scripts/a11y-ci.sh).

// Light theme ("light neon")
const lightNeonPrismTheme = {
  plain: {
    color: "#64748b",
    backgroundColor: "#f9f9fd",
  },
  styles: [
    { types: ["comment"], style: { color: "#607491", fontStyle: "italic" } },
    { types: ["string", "attr-value"], style: { color: "#04835c" } },
    { types: ["number"], style: { color: "#c74b0a" } },
    { types: ["boolean", "constant"], style: { color: "#ae5f05" } },
    { types: ["keyword-import", "imports", "module"], style: { color: "#7c3aed" } },
    { types: ["keyword", "tag"], style: { color: "#077d9a" } },
    { types: ["builtin", "class-name", "function", "attr-name", "property"], style: { color: "#d82474" } },
    { types: ["decorator"], style: { color: "#be185d" } },
    { types: ["operator", "punctuation"], style: { color: "#64748b" } },
    { types: ["variable"], style: { color: "#64748b" } },
  ],
};

// Dark theme ("Grafite Neon")
const grafiteNeonTheme = {
  plain: {
    color: "#c8ccd4",
    backgroundColor: "#18181a",
  },
  styles: [
    { types: ["comment"], style: { color: "#798197", fontStyle: "italic" } },
    { types: ["string", "attr-value", "template-string"], style: { color: "#51d0a5" } },
    { types: ["number"], style: { color: "#ff9b7d" } },
    { types: ["boolean", "constant"], style: { color: "#f7c93e" } },
    { types: ["keyword-import", "imports", "module"], style: { color: "#c792ea" } },
    { types: ["keyword", "tag"], style: { color: "#31d1e9" } },
    { types: ["builtin", "class-name", "function", "attr-name", "property"], style: { color: "#ed86bf" } },
    { types: ["decorator"], style: { color: "#e45287" } },
    { types: ["operator", "punctuation"], style: { color: "#c8ccd4" } },
    { types: ["variable"], style: { color: "#c8ccd4" } },
  ],
};

module.exports = { lightNeonPrismTheme, grafiteNeonTheme };
