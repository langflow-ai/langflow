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

  it("treats a new required input without a usable default as breaking", () => {
    const componentData = {
      type: "LanguageModelComponent",
      node: {
        edited: false,
        outputs: [],
        template: {
          code: { value: "old component code" },
          _frontend_node_flow_id: { value: "flow-1" },
          is_refresh: true,
        },
      },
    } as Parameters<typeof checkCodeValidity>[0];
    const currentTemplates = {
      LanguageModelComponent: {
        template: {
          code: { value: "current component code" },
          api_key: { value: "", required: true },
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

  // Template key sets are compared directionally, not for equality. A field only the
  // current component has is introduced with its declared default when the node is
  // rebuilt through /custom_component; a field only the saved node has holds a value
  // the updated code no longer reads. Mirrors the same cases in
  // src/lfx/tests/unit/upgrade/test_checker.py.
  const nodeWithTemplate = (template: Record<string, unknown>) =>
    ({
      type: "LanguageModelComponent",
      node: {
        edited: false,
        outputs: [],
        template,
      },
    }) as Parameters<typeof checkCodeValidity>[0];

  const templatesWithTemplate = (template: Record<string, unknown>) =>
    ({
      LanguageModelComponent: {
        template,
        outputs: [],
      },
    }) as Parameters<typeof checkCodeValidity>[1];

  it("does not treat a new optional input as breaking", () => {
    const data = nodeWithTemplate({
      code: { value: "old component code" },
    });
    const templates = templatesWithTemplate({
      code: { value: "current component code" },
      new_flag: { value: false, required: false },
    });

    expect(checkCodeValidity(data, templates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: false,
      userEdited: false,
    });
  });

  it("does not treat a new required input with a usable default as breaking", () => {
    const data = nodeWithTemplate({
      code: { value: "old component code" },
    });
    const templates = templatesWithTemplate({
      code: { value: "current component code" },
      retries: { value: 3, required: true },
    });

    expect(checkCodeValidity(data, templates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: false,
      userEdited: false,
    });
  });

  // 0, false, and [] are usable defaults; only undefined/null/"" mean there is nothing
  // to fill. Pins the guard against a truthiness rewrite.
  it("does not treat a new required input with a falsy but usable default as breaking", () => {
    for (const falsyDefault of [0, false, []]) {
      const data = nodeWithTemplate({
        code: { value: "old component code" },
      });
      const templates = templatesWithTemplate({
        code: { value: "current component code" },
        max_retries: { value: falsyDefault, required: true },
      });

      expect(checkCodeValidity(data, templates)).toMatchObject({
        outdated: true,
        blocked: false,
        breakingChange: false,
        userEdited: false,
      });
    }
  });

  // Exercises inputTypesContained: the new field has input_types, but no saved edge can
  // feed a field the node predates, so there is nothing to narrow.
  it("does not treat a new handle input as breaking", () => {
    const data = nodeWithTemplate({
      code: { value: "old component code" },
    });
    const templates = templatesWithTemplate({
      code: { value: "current component code" },
      tools: { value: "", input_types: ["Tool"] },
    });

    expect(checkCodeValidity(data, templates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: false,
      userEdited: false,
    });
  });

  it("does not treat a field the component dropped as breaking", () => {
    const data = nodeWithTemplate({
      code: { value: "old component code" },
      legacy_input: { value: "user set" },
    });
    const templates = templatesWithTemplate({
      code: { value: "current component code" },
    });

    expect(checkCodeValidity(data, templates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: false,
      userEdited: false,
    });
  });

  it("still enforces input_types containment on fields both sides have", () => {
    const data = nodeWithTemplate({
      code: { value: "old component code" },
      inp: { value: "", input_types: ["Message"] },
    });
    const templates = templatesWithTemplate({
      code: { value: "current component code" },
      inp: { value: "", input_types: ["Message", "Data"] },
    });

    expect(checkCodeValidity(data, templates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: true,
      userEdited: false,
    });
  });

  // Switching a component to tool mode replaces its outputs with a single
  // component_as_tool entry, which no component declares, so comparing the two output
  // sets always reported a breaking change.
  const toolModeNode = (template: Record<string, unknown>) =>
    ({
      type: "URLComponent",
      node: {
        edited: false,
        outputs: [
          {
            name: "component_as_tool",
            display_name: "Toolset",
            types: ["Tool"],
            method: "to_toolkit",
          },
        ],
        template,
      },
    }) as Parameters<typeof checkCodeValidity>[0];

  const urlTemplates = (template: Record<string, unknown>) =>
    ({
      URLComponent: {
        template,
        outputs: [
          {
            name: "page_results",
            display_name: "Table",
            types: ["Table"],
            method: "fetch_content",
          },
        ],
      },
    }) as Parameters<typeof checkCodeValidity>[1];

  it("does not treat a tool-mode node as breaking while the component supports tool mode", () => {
    const data = toolModeNode({
      code: { value: "old component code" },
      urls: { value: "", tool_mode: true },
      tools_metadata: {},
    });
    const templates = urlTemplates({
      code: { value: "current component code" },
      urls: { value: "", tool_mode: true },
    });

    expect(checkCodeValidity(data, templates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: false,
      userEdited: false,
    });
  });

  // Without a tool_mode input the component is not known to still produce the toolset
  // output, so the node stays breaking. Treating "no inputs at all" as tool-capable would
  // call an unfixable node safe: MockDataGenerator has no inputs and produces no toolset
  // output at runtime.
  it("treats a tool-mode node as breaking when the component declares no tool input", () => {
    const data = toolModeNode({
      code: { value: "old component code" },
      tools_metadata: {},
    });
    const templates = urlTemplates({
      code: { value: "current component code" },
    });

    expect(checkCodeValidity(data, templates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: true,
      userEdited: false,
    });
  });

  it("treats a tool-mode node as breaking once the component drops tool mode", () => {
    const data = toolModeNode({
      code: { value: "old component code" },
      urls: { value: "", tool_mode: true },
      tools_metadata: {},
    });
    const templates = urlTemplates({
      code: { value: "current component code" },
      urls: { value: "" },
    });

    expect(checkCodeValidity(data, templates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: true,
      userEdited: false,
    });
  });

  // Tool mode synthesizes exactly one output, so a duplicated name is a malformed node and
  // must keep going through the authored-output comparison.
  it("treats a node with a duplicated tool output as breaking", () => {
    const data = toolModeNode({
      code: { value: "old component code" },
      urls: { value: "", tool_mode: true },
      tools_metadata: {},
    });
    const outputs = data.node!.outputs!;
    data.node!.outputs = [outputs[0], { ...outputs[0] }];
    const templates = urlTemplates({
      code: { value: "current component code" },
      urls: { value: "", tool_mode: true },
    });

    expect(checkCodeValidity(data, templates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: true,
      userEdited: false,
    });
  });

  it("still applies the remaining checks to a tool-mode node", () => {
    const data = toolModeNode({
      code: { value: "old component code" },
      urls: { value: "", tool_mode: true, input_types: ["Message"] },
      tools_metadata: {},
    });
    const templates = urlTemplates({
      code: { value: "current component code" },
      urls: { value: "", tool_mode: true, input_types: ["Data"] },
    });

    expect(checkCodeValidity(data, templates)).toMatchObject({
      outdated: true,
      blocked: false,
      breakingChange: true,
      userEdited: false,
    });
  });
});
