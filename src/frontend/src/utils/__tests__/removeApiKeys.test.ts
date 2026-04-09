import { removeApiKeys } from "../reactflowUtils";

describe("removeApiKeys", () => {
  function makeFlow(template: Record<string, any>) {
    return {
      data: {
        nodes: [
          {
            type: "genericNode",
            data: {
              node: {
                template,
              },
            },
          },
        ],
        edges: [],
      },
    } as any;
  }

  it("preserves api_key when it is an env/global variable name", () => {
    const flow = makeFlow({
      api_key: {
        name: "api_key",
        value: "OPENAI_API_KEY",
        password: true,
        load_from_db: true,
      },
      openai_api_key: {
        name: "openai_api_key",
        value: "sk-test-123",
        password: true,
        load_from_db: false,
      },
    });

    const result = removeApiKeys(flow);
    const template = result.data!.nodes[0].data.node!.template;

    expect(template.api_key.value).toBe("OPENAI_API_KEY");
    expect(template.api_key.load_from_db).toBe(true);

    expect(template.openai_api_key.value).toBe("");
    expect(template.openai_api_key.load_from_db).toBe(false);
  });

  it("clears api_key when it contains a raw secret", () => {
    const flow = makeFlow({
      api_key: {
        name: "api_key",
        value: "sk-secret-123",
        password: true,
        load_from_db: false,
      },
    });

    const result = removeApiKeys(flow);
    const template = result.data!.nodes[0].data.node!.template;

    expect(template.api_key.value).toBe("");
    expect(template.api_key.load_from_db).toBe(false);
  });

  it("preserves non-password fields", () => {
    const flow = makeFlow({
      regular_field: {
        name: "regular_field",
        value: "keep-me",
        password: false,
      },
    });

    const result = removeApiKeys(flow);
    const template = result.data!.nodes[0].data.node!.template;

    expect(template.regular_field.value).toBe("keep-me");
  });
});
