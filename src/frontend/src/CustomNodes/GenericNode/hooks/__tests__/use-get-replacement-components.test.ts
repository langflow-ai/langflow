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

const mockData = {
  google: {
    GmailSendComponent: {
      display_name: "Send Gmail",
      template: { connection: connectionField(true) },
    },
    GoogleDriveListComponent: {
      display_name: "List Drive Files",
      template: { connection: connectionField(true) },
    },
    GmailLoaderComponent: {
      display_name: "Gmail Loader",
      template: { connection: connectionField(false) },
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
    const result = render(["google.Missing", "nodot", "unknown.Component"]);

    expect(result).toHaveLength(3);
    expect(result.every((entry) => !entry)).toBe(true);
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
      expect(result[1]).toBe("Gmail Loader");
      expect(result[2]).toBe("API Request");
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

      expect(result).toEqual(["Send Gmail", "List Drive Files", "API Request"]);
    });
  });
});
