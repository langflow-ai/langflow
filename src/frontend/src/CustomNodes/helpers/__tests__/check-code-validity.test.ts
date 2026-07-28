import { checkCodeValidity } from "../check-code-validity";

describe("checkCodeValidity", () => {
  const customComponentData = {
    type: "CustomComponent",
    node: {
      edited: false,
      template: {
        code: {
          value: "user custom code",
        },
      },
    },
  } as Parameters<typeof checkCodeValidity>[0];

  const templates = {
    CustomComponent: {
      template: {
        code: {
          value: "user custom code",
        },
      },
      outputs: [],
    },
  } as Parameters<typeof checkCodeValidity>[1];

  it("allows custom components with matching template when custom components are disabled", () => {
    // Custom components loaded from components_path have a matching template,
    // so they should not be blocked — the backend hash validation is the security gate.
    expect(
      checkCodeValidity(customComponentData, templates, false),
    ).toMatchObject({
      outdated: false,
      blocked: false,
      breakingChange: false,
      userEdited: false,
    });
  });

  it("blocks custom components with no matching template", () => {
    const emptyTemplates = {};
    expect(
      checkCodeValidity(customComponentData, emptyTemplates, false),
    ).toMatchObject({
      outdated: false,
      blocked: true,
      breakingChange: false,
      userEdited: false,
    });
  });

  it("does not surface uploaded custom components as updatable when custom components are allowed", () => {
    expect(
      checkCodeValidity(customComponentData, templates, true),
    ).toMatchObject({
      outdated: false,
      blocked: false,
      breakingChange: false,
      userEdited: false,
    });
  });

  it("ignores transient template metadata when checking breaking changes", () => {
    const componentData = {
      type: "LanguageModelComponent",
      node: {
        edited: false,
        outputs: [],
        template: {
          code: { value: "old component code" },
          _frontend_node_flow_id: { value: "flow-1" },
          _frontend_node_folder_id: { value: "folder-1" },
          is_refresh: true,
          tools_metadata: { value: [] },
        },
      },
    } as Parameters<typeof checkCodeValidity>[0];
    const currentTemplates = {
      LanguageModelComponent: {
        template: {
          code: { value: "current component code" },
        },
        outputs: [],
      },
    } as Parameters<typeof checkCodeValidity>[1];

    expect(checkCodeValidity(componentData, currentTemplates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: false,
      userEdited: false,
    });
  });

  it("still treats real component input changes as breaking", () => {
    const componentData = {
      type: "LanguageModelComponent",
      node: {
        edited: false,
        outputs: [],
        template: {
          code: { value: "old component code" },
          legacy_input: { value: "" },
          _frontend_node_flow_id: { value: "flow-1" },
          is_refresh: true,
        },
      },
    } as Parameters<typeof checkCodeValidity>[0];
    const currentTemplates = {
      LanguageModelComponent: {
        template: {
          code: { value: "current component code" },
          current_input: { value: "" },
        },
        outputs: [],
      },
    } as Parameters<typeof checkCodeValidity>[1];

    expect(checkCodeValidity(componentData, currentTemplates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: true,
      userEdited: false,
    });
  });
});
