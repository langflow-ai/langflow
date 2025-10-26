/**
 * Version utility functions for semantic versioning
 */

/**
 * Increments semantic version at the patch level
 * Examples:
 *   1.0.0 → 1.0.1
 *   1.0.9 → 1.0.10
 *   1.2.3 → 1.2.4
 *   2.5.8 → 2.5.9
 *
 * @param version - Current version string (e.g., "1.0.0") or null/undefined
 * @returns Incremented version string, or "1.0.0" if no valid version provided
 */
export function incrementPatchVersion(version: string | null | undefined): string {
  if (!version) {
    return "1.0.0"; // Default for first publish
  }

  // Try to parse semantic version (MAJOR.MINOR.PATCH)
  const semverMatch = version.match(/^(\d+)\.(\d+)\.(\d+)$/);

  if (semverMatch) {
    const [_, major, minor, patch] = semverMatch;
    const newPatch = parseInt(patch, 10) + 1;
    return `${major}.${minor}.${newPatch}`;
  }

  // Fallback: if version doesn't match semver format, default to 1.0.0
  return "1.0.0";
}

/**
 * Validates semantic version format (MAJOR.MINOR.PATCH)
 *
 * @param version - Version string to validate
 * @returns true if valid semver format, false otherwise
 */
export function isValidSemver(version: string): boolean {
  return /^\d+\.\d+\.\d+$/.test(version);
}

/**
 * Increments semantic version at the minor level (resets patch to 0)
 * Examples:
 *   1.0.9 → 1.1.0
 *   1.2.3 → 1.3.0
 *
 * @param version - Current version string
 * @returns Incremented minor version string, or "1.0.0" if no valid version provided
 */
export function incrementMinorVersion(version: string | null | undefined): string {
  if (!version) {
    return "1.0.0";
  }

  const semverMatch = version.match(/^(\d+)\.(\d+)\.(\d+)$/);

  if (semverMatch) {
    const [_, major, minor] = semverMatch;
    const newMinor = parseInt(minor, 10) + 1;
    return `${major}.${newMinor}.0`;
  }

  return "1.0.0";
}

/**
 * Increments semantic version at the major level (resets minor and patch to 0)
 * Examples:
 *   1.2.3 → 2.0.0
 *   2.5.8 → 3.0.0
 *
 * @param version - Current version string
 * @returns Incremented major version string, or "1.0.0" if no valid version provided
 */
export function incrementMajorVersion(version: string | null | undefined): string {
  if (!version) {
    return "1.0.0";
  }

  const semverMatch = version.match(/^(\d+)\.(\d+)\.(\d+)$/);

  if (semverMatch) {
    const [_, major] = semverMatch;
    const newMajor = parseInt(major, 10) + 1;
    return `${newMajor}.0.0`;
  }

  return "1.0.0";
}
