let mockAllowCustomComponents = true;
let mockComponentsToUpdate: Array<{
  id: string;
  outdated: boolean;
  blocked: boolean;
  userEdited: boolean;
}> = [];
let mockNodes: Array<{ id: string; data: { type: string } }> = [];
let mockTemplates: Record<
  string,
  { template?: { code?: { value?: string } } }
> = {};

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      componentsToUpdate: mockComponentsToUpdate,
      nodes: mockNodes,
    }),
  },
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: {
    getState: () => ({
      templates: mockTemplates,
    }),
  },
}));

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: {
    getState: () => ({
      allowCustomComponents: mockAllowCustomComponents,
    }),
  },
}));

import { isNodeOutdated } from "../customComponentGuards";

describe("customComponentGuards", () => {
  beforeEach(() => {
    mockAllowCustomComponents = true;
    mockComponentsToUpdate = [];
    mockNodes = [];
    mockTemplates = {};
  });

  it("does not block CustomComponent nodes when custom components are allowed", () => {
    mockAllowCustomComponents = true;
    mockNodes = [{ id: "node-1", data: { type: "CustomComponent" } }];

    expect(isNodeOutdated("node-1", "user custom code")).toBe(false);
  });

  it("blocks CustomComponent nodes when custom components are disabled", () => {
    mockAllowCustomComponents = false;
    mockNodes = [{ id: "node-1", data: { type: "CustomComponent" } }];

    expect(isNodeOutdated("node-1", "user custom code")).toBe(true);
  });
});
