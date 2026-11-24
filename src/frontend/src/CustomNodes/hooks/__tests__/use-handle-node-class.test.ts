import { renderHook } from "@testing-library/react";

jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => jest.fn(),
}));

jest.mock("lodash", () => ({
  cloneDeep: (o: unknown) => JSON.parse(JSON.stringify(o)),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn(),
}));

import useHandleNodeClass from "../use-handle-node-class";

describe("useHandleNodeClass", () => {
  const renderWithSetter = () => {
    const setNode = jest.fn();
    const { result } = renderHook(() => useHandleNodeClass("node-1", setNode));
    return { setNode, ...result.current };
  };

  const optionsOf = (setNode: jest.Mock) => setNode.mock.calls[0][4];

  it("saves the flow for a user-driven class change", () => {
    const { setNode, handleNodeClass } = renderWithSetter();

    handleNodeClass({ template: {} });

    expect(setNode).toHaveBeenCalledTimes(1);
    expect(optionsOf(setNode)).toBeUndefined();
  });

  // Opening a flow must not write it (#8995).
  it("does not save the flow for a refresh", () => {
    const { setNode, applyNodeClassFromRefresh } = renderWithSetter();

    applyNodeClassFromRefresh({ template: {} });

    expect(setNode).toHaveBeenCalledTimes(1);
    expect(optionsOf(setNode)).toEqual({ autoSave: false });
  });

  // Both still have to reach the canvas: withholding the save must never
  // withhold the change itself.
  it("applies the new class either way", () => {
    const { setNode, handleNodeClass, applyNodeClassFromRefresh } =
      renderWithSetter();
    const oldNode = { id: "node-1", data: { id: "node-1", node: {} } };

    handleNodeClass({ display_name: "user" });
    applyNodeClassFromRefresh({ display_name: "refresh" });

    for (const [index, expected] of [
      [0, "user"],
      [1, "refresh"],
    ] as const) {
      const updater = setNode.mock.calls[index][1] as (n: unknown) => {
        data: { node: { display_name: string } };
      };
      expect(updater(oldNode).data.node.display_name).toBe(expected);
    }
  });

  // A prop typed `(value, code?, type?) => void` takes this function directly;
  // a third parameter of another type would silently break that assignment.
  it("keeps handleNodeClass to two parameters", () => {
    const { handleNodeClass } = renderWithSetter();

    expect(handleNodeClass).toHaveLength(2);
  });
});
