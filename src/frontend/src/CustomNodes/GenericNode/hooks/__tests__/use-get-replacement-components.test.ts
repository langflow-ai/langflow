import { renderHook } from "@testing-library/react";

jest.mock("@/customization/feature-flags", () => ({
  ...jest.requireActual("@/customization/feature-flags"),
  ENABLE_INTEGRATIONS: false,
}));

// The code under test reads the flag at call time, so flipping the mocked
// export covers INT-8 turning ENABLE_INTEGRATIONS on.
const setEnableIntegrations = (value: boolean) => {
  const flags = jest.requireMock("@/customization/feature-flags") as {
    ENABLE_INTEGRATIONS: boolean;
  };
  flags.ENABLE_INTEGRATIONS = value;
};

const connectionField = (required: boolean) => ({
  type: "connection_ref",
  required,
  show: true,
  provider: "google",
});

// Mirrors the ``/api/v1/all`` shape: extension-bundle components are keyed
// ``ext:<bundle>:<ClassName>@<slot>`` and carry their legacy palette name in
// ``name``; built-in components are keyed by that name directly.
const mockData = {
  google: {
    "ext:google:GmailSendComponent@official": {
      name: "GmailSendComponent",
      display_name: "Send Gmail",
      template: { connection: connectionField(true) },
    },
    "ext:google:GoogleDriveListComponent@official": {
      name: "GoogleDriveListComponent",
      display_name: "List Drive Files",
      template: { connection: connectionField(true) },
    },
    "ext:google:GmailLoaderComponent@official": {
      name: "GmailLoaderComponent",
      display_name: "Gmail Loader",
      template: { connection: connectionField(false) },
    },
    // An @extra copy listed first must not shadow the shipped bundle.
    "ext:google:GoogleSerperAPICore@extra": {
      name: "GoogleSerperAPICore",
      display_name: "Serper (local copy)",
      template: {},
    },
    "ext:google:GoogleSerperAPICore@official": {
      name: "GoogleSerperAPICore",
      display_name: "Google Serper API",
      template: {},
    },
    "ext:google:LocalOnlyComponent@extra": {
      name: "LocalOnlyComponent",
      display_name: "Local Only",
      template: {},
    },
  },
  datastax: {
    // ``datastax.AstraDB`` names the component's ``name`` attribute, not its
    // class, so only the ``name`` field links the reference to this entry.
    "ext:datastax:AstraDBVectorStoreComponent@official": {
      name: "AstraDB",
      display_name: "Astra DB",
      template: {},
    },
  },
  data: {
    APIRequest: {
      display_name: "API Request",
      template: { url: { type: "str", required: true, show: true } },
    },
  },
};

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (selector: (state: unknown) => unknown) =>
    selector({ data: mockData }),
}));

import { useGetReplacementComponents } from "../use-get-replacement-components";

const render = (replacement?: string[]) =>
  renderHook(() => useGetReplacementComponents(replacement)).result.current;

describe("useGetReplacementComponents", () => {
  afterEach(() => {
    setEnableIntegrations(false);
  });

  it("returns an empty list without replacements", () => {
    expect(render(undefined)).toEqual([]);
    expect(render([])).toEqual([]);
  });

  it("returns a falsy entry for unknown or malformed references", () => {
    const result = render([
      "google.Missing",
      "nodot",
      "unknown.Component",
      "google.GoogleSerper",
    ]);

    expect(result).toHaveLength(4);
    expect(result.every((entry) => !entry)).toBe(true);
  });

  it("resolves built-in components by their bare key", () => {
    expect(render(["data.APIRequest"])).toEqual([
      { displayName: "API Request", filterKey: "data.APIRequest" },
    ]);
  });

  it("resolves extension-bundle components by their ext: key", () => {
    expect(render(["google.GoogleSerperAPICore"])).toEqual([
      {
        displayName: "Google Serper API",
        filterKey: "google.ext:google:GoogleSerperAPICore@official",
      },
    ]);
  });

  it("falls back to a non-official slot when that is the only copy", () => {
    expect(render(["google.LocalOnlyComponent"])).toEqual([
      {
        displayName: "Local Only",
        filterKey: "google.ext:google:LocalOnlyComponent@extra",
      },
    ]);
  });

  it("resolves references that name the component rather than its class", () => {
    expect(render(["datastax.AstraDB"])).toEqual([
      {
        displayName: "Astra DB",
        filterKey: "datastax.ext:datastax:AstraDBVectorStoreComponent@official",
      },
    ]);
  });

  it("keeps positions aligned when the first replacement is unresolved", () => {
    const result = render([
      "serpapi.Serp",
      "google.GoogleSerperAPICore",
      "data.APIRequest",
    ]);

    expect(result).toHaveLength(3);
    expect(result[0]).toBeUndefined();
    expect(result[1]?.displayName).toBe("Google Serper API");
    expect(result[2]?.displayName).toBe("API Request");
  });

  describe("with ENABLE_INTEGRATIONS off", () => {
    it("treats connection-backed replacements as not found", () => {
      const result = render([
        "google.GmailSendComponent",
        "google.GoogleDriveListComponent",
      ]);

      expect(result).toHaveLength(2);
      expect(result.every((entry) => !entry)).toBe(true);
    });

    it("keeps replacements that do not require a connection", () => {
      const result = render([
        "google.GmailSendComponent",
        "google.GmailLoaderComponent",
        "data.APIRequest",
      ]);

      expect(result[0]).toBeFalsy();
      expect(result[1]?.displayName).toBe("Gmail Loader");
      expect(result[2]?.displayName).toBe("API Request");
    });
  });

  describe("with ENABLE_INTEGRATIONS on", () => {
    beforeEach(() => {
      setEnableIntegrations(true);
    });

    it("resolves connection-backed replacements to display names", () => {
      const result = render([
        "google.GmailSendComponent",
        "google.GoogleDriveListComponent",
        "data.APIRequest",
      ]);

      expect(result.map((entry) => entry?.displayName)).toEqual([
        "Send Gmail",
        "List Drive Files",
        "API Request",
      ]);
      expect(result[0]?.filterKey).toBe(
        "google.ext:google:GmailSendComponent@official",
      );
    });
  });
});
