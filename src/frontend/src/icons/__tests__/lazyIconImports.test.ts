const mockVllmIcon = jest.fn();
const mockOpenRAGIcon = jest.fn();
const mockFigraniumIcon = jest.fn();

jest.mock("@/icons/vLLM", () => ({
  VllmIcon: mockVllmIcon,
}));

jest.mock("@/icons/OpenRAG", () => ({
  OpenRAGIcon: mockOpenRAGIcon,
}));

jest.mock("@/icons/Figranium", () => ({
  FigraniumIcon: mockFigraniumIcon,
}));

import { lazyIconsMapping } from "../lazyIconImports";

describe("lazyIconsMapping", () => {
  it("loads the vLLM provider icon", async () => {
    const { default: icon } = await lazyIconsMapping.vLLM();

    expect(icon).toBe(mockVllmIcon);
  });

  it("loads the OpenRAG icon", async () => {
    const { default: icon } = await lazyIconsMapping.OpenRAG();

    expect(icon).toBe(mockOpenRAGIcon);
  });

  it("loads the Figranium bundle icon", async () => {
    const { default: icon } = await lazyIconsMapping.Figranium();

    expect(icon).toBe(mockFigraniumIcon);
  });
});
