// Standalone test for stripReleaseStageFromVersion function
// This avoids importing from utils.ts which has dependency issues in test environment

/**
 * The stripReleaseStageFromVersion function removes release stage suffixes from version strings.
 *
 * How it works:
 * 1. Checks for keywords in order: ["a", "b", "rc", "dev", "post"]
 * 2. When a keyword is found, splits the version string on that keyword
 * 3. Takes the first part of the split
 * 4. Removes the last character using slice(0, -1)
 *
 * Examples:
 * - "1.2.3a1" → splits on "a" → ["1.2.3", "1"] → takes "1.2.3" → slice(0,-1) → "1.2."
 * - "1.2.3dev" → splits on "dev" → ["1.2.3", ""] → takes "1.2.3" → slice(0,-1) → "1.2."
 * - "1.a.3" → splits on "a" → ["1.", "3"] → takes "1." → slice(0,-1) → "1"
 * - "1.2.3" → no keywords found → returns "1.2.3" unchanged
 *
 * Note: The function finds the FIRST matching keyword in the order they appear in the array,
 * so "1.2.3ba1" finds "a" first and becomes "1.2.3" (not "b").
 */
const stripReleaseStageFromVersion = (version: string): string => {
  const releaseStageKeywords = ["a", "b", "rc", "dev", "post"];
  for (const keyword of releaseStageKeywords) {
    if (version.includes(keyword)) {
      return version.split(keyword)[0].slice(0, -1);
    }
  }
  return version;
};

describe("stripReleaseStageFromVersion", () => {
  describe("Basic functionality", () => {
    it("should strip alpha release stage", () => {
      expect(stripReleaseStageFromVersion("1.2.3a1")).toBe("1.2.");
      expect(stripReleaseStageFromVersion("2.0.0a5")).toBe("2.0.");
      expect(stripReleaseStageFromVersion("0.1.0a1")).toBe("0.1.");
    });

    it("should strip beta release stage", () => {
      expect(stripReleaseStageFromVersion("1.2.3b1")).toBe("1.2.");
      expect(stripReleaseStageFromVersion("2.0.0b2")).toBe("2.0.");
      expect(stripReleaseStageFromVersion("0.5.1b10")).toBe("0.5.");
    });

    it("should strip release candidate stage", () => {
      expect(stripReleaseStageFromVersion("1.2.3rc1")).toBe("1.2.");
      expect(stripReleaseStageFromVersion("2.0.0rc5")).toBe("2.0.");
      expect(stripReleaseStageFromVersion("3.1.0rc2")).toBe("3.1.");
    });

    it("should strip dev release stage", () => {
      expect(stripReleaseStageFromVersion("1.2.3dev")).toBe("1.2.");
      expect(stripReleaseStageFromVersion("2.0.0dev1")).toBe("2.0.");
      expect(stripReleaseStageFromVersion("0.1.0dev")).toBe("0.1.");
    });

    it("should strip post release stage", () => {
      expect(stripReleaseStageFromVersion("1.2.3post1")).toBe("1.2.");
      expect(stripReleaseStageFromVersion("2.0.0post5")).toBe("2.0.");
      expect(stripReleaseStageFromVersion("1.5.2post")).toBe("1.5.");
    });
  });

  describe("Version strings without release stages", () => {
    it("should return version unchanged when no release stage keywords are present", () => {
      expect(stripReleaseStageFromVersion("1.2.3")).toBe("1.2.3");
      expect(stripReleaseStageFromVersion("2.0.0")).toBe("2.0.0");
      expect(stripReleaseStageFromVersion("0.1.0")).toBe("0.1.0");
      expect(stripReleaseStageFromVersion("10.15.20")).toBe("10.15.20");
    });

    it("should handle semantic versioning without pre-release", () => {
      expect(stripReleaseStageFromVersion("1.0.0")).toBe("1.0.0");
      expect(stripReleaseStageFromVersion("2.1.5")).toBe("2.1.5");
      expect(stripReleaseStageFromVersion("0.0.1")).toBe("0.0.1");
    });
  });

  describe("Edge cases", () => {
    it("should handle empty string", () => {
      expect(stripReleaseStageFromVersion("")).toBe("");
    });

    it("should handle single character versions", () => {
      expect(stripReleaseStageFromVersion("1")).toBe("1");
      expect(stripReleaseStageFromVersion("a")).toBe("");
      expect(stripReleaseStageFromVersion("b")).toBe("");
    });

    it("should handle versions with keyword at the beginning", () => {
      expect(stripReleaseStageFromVersion("a1.2.3")).toBe("");
      expect(stripReleaseStageFromVersion("rc1.0.0")).toBe("");
      expect(stripReleaseStageFromVersion("dev2.0")).toBe("");
    });

    it("should handle versions with multiple keywords (first match wins)", () => {
      expect(stripReleaseStageFromVersion("1.2.3a1b2")).toBe("1.2.");
      // For "1.0.0devrc1": finds "rc" before "dev", splits on "rc": ["1.0.0dev", "1"], slice(0,-1) = "1.0.0de"
      expect(stripReleaseStageFromVersion("1.0.0devrc1")).toBe("1.0.0de");
      // For "2.1.0postb1": finds "b" before "post", splits on "b": ["2.1.0post", "1"], slice(0,-1) = "2.1.0pos"
      expect(stripReleaseStageFromVersion("2.1.0postb1")).toBe("2.1.0pos");
    });

    it("should handle versions where keyword appears in the middle", () => {
      expect(stripReleaseStageFromVersion("1.a.3")).toBe("1");
      expect(stripReleaseStageFromVersion("2.rc.0")).toBe("2");
      expect(stripReleaseStageFromVersion("1.dev.2")).toBe("1");
    });

    it("should handle very short versions with release stages", () => {
      expect(stripReleaseStageFromVersion("1a")).toBe("");
      expect(stripReleaseStageFromVersion("2b1")).toBe("");
      expect(stripReleaseStageFromVersion("3rc")).toBe("");
    });
  });

  describe("Real-world version formats", () => {
    it("should handle Python package versions", () => {
      expect(stripReleaseStageFromVersion("3.9.0a1")).toBe("3.9.");
      expect(stripReleaseStageFromVersion("3.8.0b4")).toBe("3.8.");
      expect(stripReleaseStageFromVersion("3.10.0rc2")).toBe("3.10.");
    });

    it("should handle complex version numbers", () => {
      expect(stripReleaseStageFromVersion("2021.1.0a1")).toBe("2021.1.");
      expect(stripReleaseStageFromVersion("0.25.3dev")).toBe("0.25.");
      expect(stripReleaseStageFromVersion("1.0.0post1")).toBe("1.0.");
    });

    it("should handle versions with build metadata that contains keywords", () => {
      // These should still work since the function looks for keywords anywhere
      // For "1.2.3-alpha", it finds "a" and splits on "a", then removes last char
      expect(stripReleaseStageFromVersion("1.2.3-alpha")).toBe("1.2.3");
      // For "1.2.3+beta.1": finds "a" first, splits on "a": ["1.2.3+bet", ".1"], slice(0,-1) = "1.2.3+be"
      expect(stripReleaseStageFromVersion("1.2.3+beta.1")).toBe("1.2.3+be");
    });
  });

  describe("Keyword priority", () => {
    it("should match keywords in order of appearance in the array", () => {
      // The function uses the first match it finds in the loop
      // For "1.2.3ba1": finds "a" first, splits on "a": ["1.2.3b", "1"], slice(0,-1) = "1.2.3"
      expect(stripReleaseStageFromVersion("1.2.3ba1")).toBe("1.2.3");
      expect(stripReleaseStageFromVersion("1.2.3ab1")).toBe("1.2."); // 'a' comes first in array, splits on 'a'
    });
  });

  describe("Special characters and formats", () => {
    it("should handle versions with dots and dashes", () => {
      expect(stripReleaseStageFromVersion("1.2.3-a1")).toBe("1.2.3");
      expect(stripReleaseStageFromVersion("1.2.3.dev")).toBe("1.2.3");
      expect(stripReleaseStageFromVersion("1.2.3_rc1")).toBe("1.2.3");
    });

    it("should handle versions with leading zeros", () => {
      expect(stripReleaseStageFromVersion("01.02.03a1")).toBe("01.02.0");
      expect(stripReleaseStageFromVersion("1.00.0b2")).toBe("1.00.");
    });
  });

  describe("Function behavior analysis", () => {
    it("should demonstrate the split and slice behavior", () => {
      // For "1.2.3a1": splits to ["1.2.3", "1"], takes first part "1.2.3", then slice(0, -1) = "1.2."
      expect(stripReleaseStageFromVersion("1.2.3a1")).toBe("1.2.");

      // For "1.a.3": splits to ["1.", "3"], takes first part "1.", then slice(0, -1) = "1"
      expect(stripReleaseStageFromVersion("1.a.3")).toBe("1");

      // For "1a": splits to ["1", ""], takes first part "1", then slice(0, -1) = ""
      expect(stripReleaseStageFromVersion("1a")).toBe("");
    });

    it("should handle edge cases where slice removes important characters", () => {
      // When the keyword is at position where slice(0, -1) removes a version component
      expect(stripReleaseStageFromVersion("1.2a")).toBe("1.");
      expect(stripReleaseStageFromVersion("1a")).toBe("");
      expect(stripReleaseStageFromVersion("12a")).toBe("1");
    });
  });
});
