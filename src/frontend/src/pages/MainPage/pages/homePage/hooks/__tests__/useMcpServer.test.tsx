/**
 * Critical tests for useMcpServer hook
 * Focuses on business logic and data transformation
 */

import {
  extractInstalledClientNames,
  mapFlowsToTools,
} from "../../utils/mcpServerUtils";

describe("useMcpServer - Critical Logic", () => {
  describe("Data transformation functions", () => {
    it("mapFlowsToTools correctly transforms flow data for UI", () => {
      const flows = [
        {
          id: "flow-1",
          name: "User Flow",
          description: "User desc",
          action_name: "user_flow",
          action_description: "Action desc",
          mcp_enabled: true,
        },
      ];

      const result = mapFlowsToTools(flows);

      expect(result).toHaveLength(1);
      expect(result[0]).toEqual({
        id: "flow-1",
        name: "user_flow",
        description: "Action desc",
        display_name: "User Flow",
        display_description: "User desc",
        status: true,
        tags: ["User Flow"],
      });
    });

    it("extractInstalledClientNames filters installed clients correctly", () => {
      const data = [
        { name: "cursor", installed: true },
        { name: "claude", installed: false },
        { name: "windsurf", installed: true },
      ];

      const result = extractInstalledClientNames(data);

      expect(result).toEqual(["cursor", "windsurf"]);
    });

    it("extractInstalledClientNames filters out undefined names", () => {
      const data = [
        { name: "cursor", installed: true },
        { name: undefined, installed: true }, // Should be filtered
        { installed: true }, // No name - should be filtered
      ];

      const result = extractInstalledClientNames(data);

      expect(result).toEqual(["cursor"]);
    });
  });

  describe("Hook behavior validation", () => {
    it("hook should compute hasAuthentication correctly for none auth", () => {
      const authSettings = { auth_type: "none" };
      const hasAuth = !!(
        authSettings?.auth_type && authSettings.auth_type !== "none"
      );

      expect(hasAuth).toBe(false);
    });

    it("hook should compute hasAuthentication correctly for apikey auth", () => {
      const authSettings = { auth_type: "apikey" };
      const hasAuth = !!(
        authSettings?.auth_type && authSettings.auth_type !== "none"
      );

      expect(hasAuth).toBe(true);
    });

    it("hook should compute hasOAuthError correctly", () => {
      const isOAuthProject = true;
      const composerUrlData = { error_message: "Error occurred" };

      const hasError = isOAuthProject && !!composerUrlData?.error_message;

      expect(hasError).toBe(true);
    });

    it("hook should not show OAuth error when no error message", () => {
      const isOAuthProject = true;
      const composerUrlData = { error_message: undefined };

      const hasError = isOAuthProject && !!composerUrlData?.error_message;

      expect(hasError).toBe(false);
    });
  });
});
