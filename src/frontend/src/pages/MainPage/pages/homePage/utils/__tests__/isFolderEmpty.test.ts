import type { FlowType } from "@/types/flow";
import { isFolderEmpty } from "../isFolderEmpty";

const buildFlow = (overrides: Partial<FlowType> = {}): FlowType =>
  ({
    id: overrides.id ?? "flow-1",
    name: overrides.name ?? "Flow",
    folder_id: overrides.folder_id ?? "folder-A",
    is_component: overrides.is_component ?? false,
    data: null,
    description: "",
    endpoint_name: "",
    locked: false,
  }) as FlowType;

describe("isFolderEmpty", () => {
  it("should_return_true_when_both_store_and_query_report_no_content", () => {
    expect(
      isFolderEmpty({
        flows: [],
        folderId: "folder-B",
        folderTotal: 0,
        enableMcp: false,
      }),
    ).toBe(true);
  });

  it("should_return_false_when_store_has_flow_in_folder_but_query_is_still_stale", () => {
    // Arrange — simulates the drag-drop scenario where saveFlow.onSuccess
    // has already updated the global store but the folder query cache for
    // the destination hasn't been refetched yet.
    const flows = [buildFlow({ id: "flow-1", folder_id: "folder-B" })];

    // Act
    const result = isFolderEmpty({
      flows,
      folderId: "folder-B",
      folderTotal: 0,
      enableMcp: false,
    });

    // Assert — if the store knows about the move, we must not render the
    // empty state, even when the query cache is still reporting zero.
    expect(result).toBe(false);
  });

  it("should_return_false_when_query_has_content_but_store_is_still_stale", () => {
    // Arrange — opposite stale direction: the folder query already has
    // the fresh total from the server (e.g. first navigation to a
    // previously-empty destination), but the global store hasn't been
    // invalidated yet.
    const flows = [buildFlow({ id: "flow-1", folder_id: "folder-A" })];

    // Act
    const result = isFolderEmpty({
      flows,
      folderId: "folder-B",
      folderTotal: 1,
      enableMcp: false,
    });

    // Assert — a non-zero folder total must also prevent the empty state.
    expect(result).toBe(false);
  });

  it("should_return_true_when_store_only_has_components_and_mcp_mode_excludes_them", () => {
    // In ENABLE_MCP mode, only non-component flows count as content.
    const flows = [
      buildFlow({ id: "comp-1", folder_id: "folder-A", is_component: true }),
    ];

    const result = isFolderEmpty({
      flows,
      folderId: "folder-A",
      folderTotal: 0,
      enableMcp: true,
    });

    expect(result).toBe(true);
  });

  it("should_ignore_component_flag_when_mcp_disabled", () => {
    const flows = [
      buildFlow({ id: "comp-1", folder_id: "folder-A", is_component: true }),
    ];

    const result = isFolderEmpty({
      flows,
      folderId: "folder-A",
      folderTotal: 0,
      enableMcp: false,
    });

    expect(result).toBe(false);
  });

  it("should_return_true_when_flows_store_is_still_loading", () => {
    expect(
      isFolderEmpty({
        flows: undefined,
        folderId: "folder-A",
        folderTotal: undefined,
        enableMcp: false,
      }),
    ).toBe(true);
  });
});
