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
    // Arrange — reproduz exatamente o cenário do bug:
    // AUTO_LOGIN=false, usuário novo no primeiro login.
    // O endpoint /flows/ retorna [] (user_id == current_user.id não bate com os starters).
    // O endpoint /basic_examples/ retorna os flows do STARTER_FOLDER global (user_id=None).
    // O usuário tem apenas o default folder criado em get_or_create_default_folder.
    const flows: FlowType[] = [];
    const examples: FlowType[] = [
      makeFlow("starter-1"),
      makeFlow("starter-2"),
      makeFlow("starter-3"),
    ];
    const folders: FolderType[] = [makeFolder("default-folder-id")];

    // Act
    const result = shouldShowMainContent(flows, examples, folders);

    // Assert — tem que ser false para a Welcome page aparecer
    expect(result).toBe(false);
  });

  it("should_show_welcome_page_when_user_flows_are_all_starter_examples_with_auto_login_on", () => {
    // AUTO_LOGIN=true: o endpoint /flows/ retorna os starters via OR (user_id is None).
    // Logo, flows e examples têm os mesmos ids.
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
    // AUTO_LOGIN=false user criando seu primeiro flow customizado.
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
