import {
  getV2WorkflowsCurlCode,
  getV2WorkflowsJsCode,
  getV2WorkflowsPythonCode,
} from "../get-v2-workflows-code";

// getBaseUrl() resolves the host through customGetHostProtocol.
jest.mock("@/customization/utils/custom-get-host-protocol", () => ({
  customGetHostProtocol: () => ({
    protocol: "https:",
    host: "localhost:3000",
  }),
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_DATASTAX_LANGFLOW: false,
}));

const URL = "https://localhost:3000/api/v2/workflows";
const FLOW_ID = "67ccd2be-17f0-8190-81ff-3bb2cf6508e6";

const baseOptions = {
  flowId: FLOW_ID,
  inputValue: "Hello",
  tweaks: undefined,
  shouldDisplayApiKey: false,
};

const allGenerators = [
  ["curl", getV2WorkflowsCurlCode],
  ["python", getV2WorkflowsPythonCode],
  ["js", getV2WorkflowsJsCode],
] as const;

describe("v2 workflows generators (shared behavior)", () => {
  it.each(allGenerators)(
    "%s: uses outcome titles with descriptions and no API jargon",
    (_name, gen) => {
      const { steps } = gen(baseOptions);
      expect(steps).toHaveLength(2);
      expect(steps[0].title).toBe("Get the full result");
      expect(steps[1].title).toBe("Stream the result as it runs");
      // every step explains itself in plain language
      expect(
        steps[0].description && steps[0].description.length,
      ).toBeGreaterThan(20);
      expect(
        steps[1].description && steps[1].description.length,
      ).toBeGreaterThan(20);
      const all = steps
        .map((s) => `${s.title} ${s.description} ${s.code}`)
        .join("\n");
      // the words the product owner could not parse never appear as labels
      expect(all).not.toContain("Synchronous");
      expect(steps.map((s) => s.title).join()).not.toMatch(/AG-UI/);
      // the placeholder key is gone in favor of an env var
      expect(all).not.toContain("YOUR_API_KEY_HERE");
    },
  );

  it.each(allGenerators)(
    "%s: minimal body has no mode/stream_protocol; stream sets mode only",
    (_name, gen) => {
      const [sync, stream] = gen(baseOptions).steps;
      expect(sync.code).toContain(URL);
      expect(sync.code).toContain(`"flow_id": "${FLOW_ID}"`);
      expect(sync.code).toContain(`"input_value": "Hello"`);
      expect(sync.code).not.toContain('"mode"');
      expect(sync.code).not.toContain("stream_protocol");
      expect(stream.code).toContain('"mode": "stream"');
      expect(stream.code).not.toContain("stream_protocol");
    },
  );

  it.each(allGenerators)(
    "%s: streaming consumes the langflow 'event' field, not 'type'",
    (_name, gen) => {
      const stream = gen(baseOptions).steps[1].code;
      expect(stream).toContain("event");
      expect(stream).toContain("add_message");
      expect(stream).toContain("token");
      expect(stream).toContain("end");
      // the old (wrong) agui 'type' discriminator must be gone
      expect(stream).not.toMatch(/\.type|"type"/);
    },
  );

  it.each(allGenerators)(
    "%s: omits the key by default and uses an env var when authenticated",
    (_name, gen) => {
      expect(gen(baseOptions).steps[0].code).not.toContain("x-api-key");
      const withKey = gen({ ...baseOptions, shouldDisplayApiKey: true })
        .steps[0].code;
      expect(withKey).toContain("x-api-key");
      expect(withKey).toMatch(/LANGFLOW_API_KEY/);
    },
  );

  it.each(allGenerators)(
    "%s: sync reads the answer from output.text, not a component-id loop",
    (_name, gen) => {
      const sync = gen(baseOptions).steps[0].code;
      expect(sync).toContain("output.text");
      // the unpredictable component-id map is no longer the access path
      expect(sync).not.toContain(".values()");
      expect(sync).not.toContain("Object.values(result.outputs)");
      // the component id never leaks as a field the caller has to read
      expect(sync).not.toContain("component_id");
    },
  );
});

describe("getV2WorkflowsCurlCode", () => {
  it("uses POST and the streaming step uses -N for an unbuffered stream", () => {
    const [sync, stream] = getV2WorkflowsCurlCode(baseOptions).steps;
    expect(sync.code).toContain("curl -X POST");
    expect(stream.code).toContain("curl -N -X POST");
  });

  it("includes tweaks only when provided", () => {
    expect(getV2WorkflowsCurlCode(baseOptions).steps[0].code).not.toContain(
      "tweaks",
    );
    const withTweaks = getV2WorkflowsCurlCode({
      ...baseOptions,
      tweaks: { "ChatInput-abc": { input_value: "Hi" } },
    }).steps[0].code;
    expect(withTweaks).toContain("tweaks");
    expect(withTweaks).toContain("ChatInput-abc");
  });

  it("sync peek shows the shape: output{reason,text,source} + session_id, content but no metadata/component_id field", () => {
    const sync = getV2WorkflowsCurlCode(baseOptions).steps[0].code;
    expect(sync).toContain('"output"');
    expect(sync).toContain('"reason"');
    expect(sync).toContain("output.text");
    expect(sync).toContain("session_id");
    expect(sync).toContain("content");
    expect(sync).not.toContain("component_id");
    expect(sync).not.toContain("metadata");
  });
});

describe("getV2WorkflowsPythonCode", () => {
  it("imports os only when the api key env var is used", () => {
    expect(getV2WorkflowsPythonCode(baseOptions).steps[0].code).not.toContain(
      "import os",
    );
    const withKey = getV2WorkflowsPythonCode({
      ...baseOptions,
      shouldDisplayApiKey: true,
    }).steps[0].code;
    expect(withKey).toContain("import os");
    expect(withKey).toContain('os.environ["LANGFLOW_API_KEY"]');
  });
});

describe("getV2WorkflowsJsCode", () => {
  it("uses fetch for sync and a reader for streaming", () => {
    const [sync, stream] = getV2WorkflowsJsCode(baseOptions).steps;
    expect(sync.code).toContain(`fetch("${URL}"`);
    expect(stream.code).toContain("getReader()");
  });
});
