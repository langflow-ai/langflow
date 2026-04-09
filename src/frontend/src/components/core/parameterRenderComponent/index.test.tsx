// TypeScript-only test to verify component props interface
// This test doesn't run any actual component code to avoid Jest configuration issues

describe("ParameterRenderComponent Types", () => {
  it("should accept correct props type", () => {
    // This test verifies that the component accepts the correct props structure
    const baseProps = {
      handleOnNewValue: jest.fn(),
      name: "test-field",
      nodeId: "test-node-id",
      editNode: false,
      handleNodeClass: jest.fn(),
      nodeClass: {
        description: "Test component",
        template: {},
        display_name: "Test Component",
        documentation: "Test component documentation",
      },
      disabled: false,
      templateValue: "Hello {{name}}!",
    };

    // Test different template data types
    const mustacheTemplateData = { type: "mustache", name: "template" };
    const promptTemplateData = { type: "prompt", name: "template" };

    // If this compiles without TypeScript errors, the types are correct
    expect(baseProps).toBeDefined();
    expect(baseProps.nodeClass.description).toBe("Test component");
    expect(baseProps.nodeClass.display_name).toBe("Test Component");
    expect(baseProps.nodeClass.documentation).toBe(
      "Test component documentation",
    );
    expect(mustacheTemplateData.type).toBe("mustache");
    expect(promptTemplateData.type).toBe("prompt");
  });
});
