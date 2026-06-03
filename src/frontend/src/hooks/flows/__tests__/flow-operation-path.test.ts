import {
  deleteValueAtPath,
  getValueAtPath,
  setValueAtPath,
} from "../flow-operation-path";

describe("flow-operation-path", () => {
  it("sets scalar null array and object values", () => {
    const target = { data: { label: "old" } };

    setValueAtPath(target, ["data", "label"], null);
    setValueAtPath(target, ["data", "items"], [1, 2]);
    setValueAtPath(target, ["data", "config"], { enabled: true });

    expect(target).toEqual({
      data: {
        label: null,
        items: [1, 2],
        config: { enabled: true },
      },
    });
  });

  it("replaces existing array indexes", () => {
    const target = { outputs: [{ selected: "a" }, { selected: "b" }] };

    setValueAtPath(target, ["outputs", 1, "selected"], null);

    expect(target.outputs[1]?.selected).toBeNull();
  });

  it("deletes object keys and treats missing final keys as absent", () => {
    const target = { data: { customColor: "#fff" } };

    expect(getValueAtPath(target, ["data", "customColor"])).toEqual({
      exists: true,
      value: "#fff",
    });
    deleteValueAtPath(target, ["data", "customColor"]);

    expect(getValueAtPath(target, ["data", "customColor"])).toEqual({
      exists: false,
    });
    deleteValueAtPath(target, ["data", "customColor"]);
    expect(target).toEqual({ data: {} });
  });

  it("rejects missing parents and array deletes", () => {
    expect(() => setValueAtPath({}, ["data", "label"], "x")).toThrow(
      "parent path does not exist",
    );
    expect(() => deleteValueAtPath({ items: ["a"] }, ["items", 0])).toThrow(
      "delete only supports object properties",
    );
  });
});
