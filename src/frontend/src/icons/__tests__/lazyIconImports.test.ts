const mockVllmIcon = jest.fn();

jest.mock("@/icons/vLLM", () => ({
  VllmIcon: mockVllmIcon,
}));

import { lazyIconsMapping } from "../lazyIconImports";

describe("lazyIconsMapping", () => {
  it("loads the vLLM provider icon", async () => {
    const { default: icon } = await lazyIconsMapping.vLLM();

    expect(icon).toBe(mockVllmIcon);
  });
});
