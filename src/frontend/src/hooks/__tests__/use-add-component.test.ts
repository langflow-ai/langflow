import { renderHook } from "@testing-library/react";
import { useStoreApi } from "@xyflow/react";
import { track } from "@/customization/utils/analytics";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "@/types/api";
import { getNodeId } from "@/utils/reactflowUtils";
import { getNodeRenderType } from "@/utils/utils";
import { useAddComponent } from "../use-add-component";

// Mock dependencies
jest.mock("@xyflow/react");
jest.mock("@/stores/flowStore");
jest.mock("@/customization/utils/analytics");
jest.mock("@/utils/reactflowUtils");
jest.mock("@/utils/utils");

let mockCloudOnly = false;
jest.mock("@/stores/cloudModeStore", () => ({
  useCloudModeStore: (
    selector: (state: {
      cloudOnly: boolean;
      setCloudOnly: jest.Mock;
    }) => unknown,
  ) => selector({ cloudOnly: mockCloudOnly, setCloudOnly: jest.fn() }),
}));

describe("useAddComponent", () => {
  const mockPaste = jest.fn();
  const mockGetFilterEdge = jest.fn();
  const mockGetState = jest.fn();
  const mockStore = {
    getState: mockGetState,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockCloudOnly = false;

    (useStoreApi as jest.Mock).mockReturnValue(mockStore);
    (useFlowStore as unknown as jest.Mock).mockImplementation((selector) => {
      const state = {
        paste: mockPaste,
        getFilterEdge: mockGetFilterEdge,
        filterType: null,
      };
      return selector(state);
    });

    mockGetState.mockReturnValue({
      height: 800,
      width: 1200,
      transform: [100, 50, 1],
    });

    (getNodeId as jest.Mock).mockReturnValue("node-123");
    (getNodeRenderType as jest.Mock).mockReturnValue("genericnode");
  });

  it("should add component with default centered position", () => {
    const mockComponent: APIClassType = {
      display_name: "Test Component",
      description: "Test description",
      template: {},
      outputs: [],
    } as unknown as APIClassType;

    const { result } = renderHook(() => useAddComponent());
    const addComponent = result.current;

    addComponent(mockComponent, "TestType");

    expect(track).toHaveBeenCalledWith("Component Added", {
      componentType: "Test Component",
    });

    expect(getNodeId).toHaveBeenCalledWith("TestType");

    expect(mockPaste).toHaveBeenCalledWith(
      {
        nodes: [
          expect.objectContaining({
            id: "node-123",
            type: "genericnode",
            position: { x: 0, y: 0 },
            data: expect.objectContaining({
              node: mockComponent,
              showNode: true,
              type: "TestType",
              id: "node-123",
            }),
          }),
        ],
        edges: [],
      },
      expect.objectContaining({
        x: expect.any(Number),
        y: expect.any(Number),
        paneX: expect.any(Number),
        paneY: expect.any(Number),
      }),
    );
  });

  it("should add component with custom position", () => {
    const mockComponent: APIClassType = {
      display_name: "Test Component",
      description: "Test description",
      template: {},
      outputs: [],
    } as unknown as APIClassType;

    const customPosition = { x: 100, y: 200 };

    const { result } = renderHook(() => useAddComponent());
    const addComponent = result.current;

    addComponent(mockComponent, "TestType", customPosition);

    expect(mockPaste).toHaveBeenCalledWith(
      expect.objectContaining({
        nodes: expect.any(Array),
        edges: [],
      }),
      customPosition,
    );
  });

  it("should show node when component is not minimized", () => {
    const mockComponent: APIClassType = {
      display_name: "Test Component",
      description: "Test description",
      template: {},
      outputs: [],
      minimized: false,
    } as unknown as APIClassType;

    const { result } = renderHook(() => useAddComponent());
    const addComponent = result.current;

    addComponent(mockComponent, "TestType");

    expect(mockPaste).toHaveBeenCalledWith(
      {
        nodes: [
          expect.objectContaining({
            data: expect.objectContaining({
              showNode: true,
            }),
          }),
        ],
        edges: [],
      },
      expect.any(Object),
    );
  });

  it("should hide node when component is minimized", () => {
    const mockComponent: APIClassType = {
      display_name: "Test Component",
      description: "Test description",
      template: {},
      outputs: [],
      minimized: true,
    } as unknown as APIClassType;

    const { result } = renderHook(() => useAddComponent());
    const addComponent = result.current;

    addComponent(mockComponent, "TestType");

    expect(mockPaste).toHaveBeenCalledWith(
      {
        nodes: [
          expect.objectContaining({
            data: expect.objectContaining({
              showNode: false,
            }),
          }),
        ],
        edges: [],
      },
      expect.any(Object),
    );
  });

  it("should set selected_output when filterType matches component output", () => {
    const mockComponent: APIClassType = {
      display_name: "Test Component",
      description: "Test description",
      template: {},
      outputs: [
        { name: "output1", types: ["string", "text"] },
        { name: "output2", types: ["number"] },
      ],
    } as unknown as APIClassType;

    (useFlowStore as unknown as jest.Mock).mockImplementation((selector) => {
      const state = {
        paste: mockPaste,
        getFilterEdge: mockGetFilterEdge,
        filterType: { type: "string" },
      };
      return selector(state);
    });

    const { result } = renderHook(() => useAddComponent());
    const addComponent = result.current;

    addComponent(mockComponent, "TestType");

    expect(mockPaste).toHaveBeenCalledWith(
      {
        nodes: [
          expect.objectContaining({
            data: expect.objectContaining({
              selected_output: "output1",
            }),
          }),
        ],
        edges: [],
      },
      expect.any(Object),
    );
  });

  it("should not set selected_output when filterType does not match any output", () => {
    const mockComponent: APIClassType = {
      display_name: "Test Component",
      description: "Test description",
      template: {},
      outputs: [
        { name: "output1", types: ["string"] },
        { name: "output2", types: ["number"] },
      ],
    } as unknown as APIClassType;

    (useFlowStore as unknown as jest.Mock).mockImplementation((selector) => {
      const state = {
        paste: mockPaste,
        getFilterEdge: mockGetFilterEdge,
        filterType: { type: "boolean" },
      };
      return selector(state);
    });

    const { result } = renderHook(() => useAddComponent());
    const addComponent = result.current;

    addComponent(mockComponent, "TestType");

    expect(mockPaste).toHaveBeenCalledWith(
      {
        nodes: [
          expect.objectContaining({
            data: expect.not.objectContaining({
              selected_output: expect.anything(),
            }),
          }),
        ],
        edges: [],
      },
      expect.any(Object),
    );
  });

  it("should calculate centered position based on viewport transform", () => {
    mockGetState.mockReturnValue({
      height: 1000,
      width: 1500,
      transform: [200, 100, 2], // x, y, zoom
    });

    const mockComponent: APIClassType = {
      display_name: "Test Component",
      description: "Test description",
      template: {},
      outputs: [],
    } as unknown as APIClassType;

    const { result } = renderHook(() => useAddComponent());
    const addComponent = result.current;

    addComponent(mockComponent, "TestType");

    // With zoom = 2, the calculation should be:
    // centerX = -200 * (1/2) + (1500 * (1/2)) / 2 = -100 + 375 = 275
    // centerY = -100 * (1/2) + (1000 * (1/2)) / 2 = -50 + 250 = 200

    expect(mockPaste).toHaveBeenCalledWith(
      expect.any(Object),
      expect.objectContaining({
        paneX: 275,
        paneY: 200,
      }),
    );
  });

  it("should handle component with no outputs", () => {
    const mockComponent: APIClassType = {
      display_name: "Test Component",
      description: "Test description",
      template: {},
    } as unknown as APIClassType;

    const { result } = renderHook(() => useAddComponent());
    const addComponent = result.current;

    addComponent(mockComponent, "TestType");

    expect(mockPaste).toHaveBeenCalledWith(
      {
        nodes: [
          expect.objectContaining({
            data: expect.not.objectContaining({
              selected_output: expect.anything(),
            }),
          }),
        ],
        edges: [],
      },
      expect.any(Object),
    );
  });

  it("should apply cloud default overrides to new nodes without mutating the source component", () => {
    mockCloudOnly = true;

    const mockComponent: APIClassType = {
      display_name: "Qdrant",
      description: "Qdrant vector store",
      template: {
        url: {
          type: "str",
          value: "http://localhost:6333",
          placeholder: "Local URL",
        },
      },
      metadata: {
        cloud_default_overrides: {
          url: {
            value: "",
            placeholder: "Enter your cloud Qdrant URL",
          },
        },
      },
      outputs: [],
    } as unknown as APIClassType;

    const { result } = renderHook(() => useAddComponent());
    const addComponent = result.current;

    addComponent(mockComponent, "Qdrant");

    const pastedNode = mockPaste.mock.calls[0][0].nodes[0].data.node;

    expect(pastedNode).not.toBe(mockComponent);
    expect(pastedNode.template.url.value).toBe("");
    expect(pastedNode.template.url.placeholder).toBe(
      "Enter your cloud Qdrant URL",
    );
    expect(mockComponent.template.url.value).toBe("http://localhost:6333");
    expect(mockComponent.template.url.placeholder).toBe("Local URL");
  });

  it("should replace cloud-incompatible sortable list defaults on new nodes without mutating the source component", () => {
    mockCloudOnly = true;

    const localOption = { name: "Local", icon: "hard-drive" };
    const awsOption = { name: "AWS", icon: "Amazon" };
    const googleDriveOption = { name: "Google Drive", icon: "google" };

    const mockComponent: APIClassType = {
      display_name: "Write File",
      description: "Save data to file",
      template: {
        storage_location: {
          type: "sortableList",
          value: [localOption],
          options: [localOption, awsOption, googleDriveOption],
          limit: 1,
        },
      },
      metadata: {
        cloud_incompatible_options: {
          storage_location: ["Local"],
        },
      },
      outputs: [],
    } as unknown as APIClassType;

    const { result } = renderHook(() => useAddComponent());
    const addComponent = result.current;

    addComponent(mockComponent, "SaveToFile");

    const pastedNode = mockPaste.mock.calls[0][0].nodes[0].data.node;

    expect(pastedNode).not.toBe(mockComponent);
    expect(pastedNode.template.storage_location.value).toEqual([awsOption]);
    expect(mockComponent.template.storage_location.value).toEqual([
      localOption,
    ]);
  });
});
