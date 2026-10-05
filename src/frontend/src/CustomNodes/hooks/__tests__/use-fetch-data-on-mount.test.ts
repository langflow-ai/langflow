import { renderHook } from "@testing-library/react";
import type { APIClassType } from "@/types/api";

const mockMutateTemplate = jest.fn();

jest.mock("../../helpers/mutate-template", () => ({
  mutateTemplate: (...args: unknown[]) => mockMutateTemplate(...args),
}));

jest.mock("../../../stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setErrorData: jest.fn() }),
}));

import useFetchDataOnMount from "../use-fetch-data-on-mount";

const nodeWithRefreshableField = (): APIClassType =>
  ({
    template: {
      model_name: {
        real_time_refresh: true,
        options: [],
        value: "",
      },
    },
  }) as unknown as APIClassType;

describe("useFetchDataOnMount", () => {
  beforeEach(() => mockMutateTemplate.mockClear());

  it("refreshes the template on mount", () => {
    renderHook(() =>
      useFetchDataOnMount(
        nodeWithRefreshableField(),
        "node-1",
        jest.fn(),
        "model_name",
        {} as never,
      ),
    );

    expect(mockMutateTemplate).toHaveBeenCalledTimes(1);
  });

  // Whether that refresh saves the flow is decided by the setter the caller
  // hands in - NodeInputField passes the non-saving one (#8995), covered in
  // use-handle-node-class.test.ts. This hook must pass it through untouched.
  it("applies the refresh through the setter it was given", () => {
    const setNodeClass = jest.fn();

    renderHook(() =>
      useFetchDataOnMount(
        nodeWithRefreshableField(),
        "node-1",
        setNodeClass,
        "model_name",
        {} as never,
      ),
    );

    expect(mockMutateTemplate.mock.calls[0][3]).toBe(setNodeClass);
  });

  describe("a node with a model and an empty API key", () => {
    const modelNode = (): APIClassType =>
      ({
        template: {
          model: { real_time_refresh: true, options: [], value: "" },
          api_key: { real_time_refresh: true, value: "" },
        },
      }) as unknown as APIClassType;

    const mountField = (node: APIClassType, name: string) =>
      renderHook(() =>
        useFetchDataOnMount(node, "node-1", jest.fn(), name, {} as never),
      );

    it("prefills the key through the model refresh only", () => {
      const node = modelNode();
      mountField(node, "model");
      mountField(node, "api_key");

      expect(mockMutateTemplate).toHaveBeenCalledTimes(1);
      expect(mockMutateTemplate.mock.calls[0][6]).toBe("model");
    });

    it("still refreshes the key of a node without a model field", () => {
      const node = {
        template: { api_key: { real_time_refresh: true, value: "" } },
      } as unknown as APIClassType;
      mountField(node, "api_key");

      expect(mockMutateTemplate).toHaveBeenCalledTimes(1);
      expect(mockMutateTemplate.mock.calls[0][6]).toBe("api_key");
    });
  });
});
