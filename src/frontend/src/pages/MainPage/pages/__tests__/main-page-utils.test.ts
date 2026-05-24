import type { FlowType } from "@/types/flow";
import type { FolderType } from "../../entities";
import { shouldShowMainContent } from "../main-page-utils";

const makeFlow = (id: string): FlowType =>
  ({ id, name: `flow-${id}`, is_component: false }) as FlowType;

const makeFolder = (id: string, name = "default"): FolderType => ({
  id,
  name,
  description: "",
  parent_id: "",
  flows: [],
  components: [],
});

describe("shouldShowMainContent", () => {
  it("should_show_welcome_page_when_new_user_has_no_flows_and_examples_are_global_with_auto_login_off", () => {
    // Arrange — reproduces the exact bug scenario:
    // AUTO_LOGIN=false, new user on first login.
    // /flows/ returns [] (user_id == current_user.id doesn't match starters).
    // /basic_examples/ returns global STARTER_FOLDER flows (user_id=None).
    // User only has the default folder from get_or_create_default_folder.
    const flows: FlowType[] = [];
    const examples: FlowType[] = [
      makeFlow("starter-1"),
      makeFlow("starter-2"),
      makeFlow("starter-3"),
    ];
    const folders: FolderType[] = [makeFolder("default-folder-id")];

    // Act
    const result = shouldShowMainContent(flows, examples, folders);

    // Assert — must be false so the Welcome page is shown
    expect(result).toBe(false);
  });

  it("should_show_welcome_page_when_user_flows_are_all_starter_examples_with_auto_login_on", () => {
    // AUTO_LOGIN=true: /flows/ returns starters via OR (user_id is None).
    // So flows and examples share the same ids.
    const sharedFlows = [
      makeFlow("starter-1"),
      makeFlow("starter-2"),
      makeFlow("starter-3"),
    ];
    const folders: FolderType[] = [makeFolder("default-folder-id")];

    const result = shouldShowMainContent(sharedFlows, sharedFlows, folders);

    expect(result).toBe(false);
  });

  it("should_show_main_content_when_user_has_at_least_one_custom_flow_besides_examples", () => {
    const examples = [makeFlow("starter-1"), makeFlow("starter-2")];
    const flows = [...examples, makeFlow("user-custom-1")];
    const folders = [makeFolder("default-folder-id")];

    const result = shouldShowMainContent(flows, examples, folders);

    expect(result).toBe(true);
  });

  it("should_show_main_content_when_user_has_more_than_one_folder", () => {
    const flows: FlowType[] = [];
    const examples = [makeFlow("starter-1")];
    const folders = [
      makeFolder("default-folder-id"),
      makeFolder("extra-folder-id", "Extra"),
    ];

    const result = shouldShowMainContent(flows, examples, folders);

    expect(result).toBe(true);
  });

  it("should_show_welcome_page_when_user_has_no_flows_and_no_examples_and_single_folder", () => {
    const result = shouldShowMainContent([], [], [makeFolder("default")]);

    expect(result).toBe(false);
  });

  it("should_show_main_content_when_auto_login_off_user_creates_only_a_single_custom_flow", () => {
    // AUTO_LOGIN=false user creating their first custom flow.
    const flows = [makeFlow("my-first-flow")];
    const examples = [
      makeFlow("starter-1"),
      makeFlow("starter-2"),
      makeFlow("starter-3"),
    ];
    const folders = [makeFolder("default-folder-id")];

    const result = shouldShowMainContent(flows, examples, folders);

    expect(result).toBe(true);
  });
});
