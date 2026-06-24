// IBM Equal Access accessibility-checker configuration
// https://github.com/IBMa/equal-access/tree/master/accessibility-checker
module.exports = {
  // Pinned rule archive — keeps CI deterministic (IBM updates "latest"
  // independently of this repo). Bump deliberately, like any dependency.
  ruleArchive: "19May2026",
  // IBM_Accessibility maps to WCAG 2.1 AA + IBM requirements
  policies: ["IBM_Accessibility"],
  // Fail levels: what makes the scan exit non-zero (kept to real violations)
  failLevels: ["violation"],
  // Report levels: what gets written to the reports
  reportLevels: [
    "violation",
    "potentialviolation",
    "recommendation",
    "potentialrecommendation",
    "manual",
  ],
  outputFormat: ["json"],
  outputFolder: "a11y-results",
  // Don't fail the run when a newer rule archive exists
  ignoreArchiveVersionCheck: true,
};
