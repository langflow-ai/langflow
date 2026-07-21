import type { APIClassType } from "@/types/api";
import { mutateTemplate } from "../mutate-template";

describe("mutateTemplate", () => {
  it("sends Tool Mode changes immediately", async () => {
    const node = {
      template: {
        code: { value: "component source" },
      },
      outputs: [],
      tool_mode: false,
    } as unknown as APIClassType;
    const updatedNode = {
      template: node.template,
      outputs: [],
      last_updated: "2026-07-21T16:30:00.000Z",
    } as unknown as APIClassType;
    const mutateAsync = jest.fn().mockResolvedValue(updatedNode);
    const setNodeClass = jest.fn();

    await mutateTemplate(
      true,
      "mcp-tools-node",
      node,
      setNodeClass,
      { mutateAsync } as never,
      jest.fn(),
      "tool_mode",
      jest.fn(),
      true,
    );

    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ value: true, tool_mode: true }),
    );
    expect(setNodeClass).toHaveBeenCalledWith(
      expect.objectContaining({ tool_mode: true }),
    );
  });
});
