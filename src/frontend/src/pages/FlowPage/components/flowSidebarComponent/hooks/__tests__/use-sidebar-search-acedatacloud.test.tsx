import fs from "node:fs";
import path from "node:path";
import { renderHook, waitFor } from "@testing-library/react";
import type { APIDataType } from "@/types/api";
import { useSidebarSearch } from "../useSidebarSearch";

// Generated from real bundle forms; the Python bundle test checks this fixture
// against the current component classes so the two sides cannot drift silently.
const forms = JSON.parse(
  fs.readFileSync(
    path.resolve(
      __dirname,
      "../../../../../../../../bundles/acedatacloud/tests/fixtures/service-search.json",
    ),
    "utf8",
  ),
) as APIDataType;

describe("Ace service discovery in the component palette", () => {
  it.each([
    ["suno", "SunoGenerateComponent", "SunoRetrieveTaskComponent"],
    ["seedance", "SeedanceGenerateComponent", "SeedanceRetrieveTaskComponent"],
    [
      "happyhorse",
      "HappyHorseGenerateComponent",
      "HappyHorseRetrieveTaskComponent",
    ],
    ["gpt image", "GPTImageGenerateComponent", "GPTImageRetrieveTaskComponent"],
    [
      "nano banana",
      "NanoBananaGenerateComponent",
      "NanoBananaRetrieveTaskComponent",
    ],
  ])(
    "finds %s generation and the same-task reader",
    async (term, generate, retrieve) => {
      const { result } = renderHook(() =>
        useSidebarSearch({
          baseData: forms,
          debouncedSearch: term,
          data: forms,
          mcpServers: undefined,
          mcpSuccess: false,
        }),
      );

      await waitFor(() => expect(result.current.searchResults).not.toBeNull());
      const matches = result.current.searchFilteredData.ace_data_cloud;
      for (const name of [generate, retrieve]) {
        const component = matches[`ext:ace_data_cloud:${name}@official`];
        expect(component).toBeDefined();
        expect(component.display_name).toContain("by Ace Data Cloud");
      }
    },
  );
});
