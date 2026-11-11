const mockVllmIcon = jest.fn();
const mockOpenRAGIcon = jest.fn();
const mockFigraniumIcon = jest.fn();
const mockKeenableIcon = jest.fn();
const mockPiloterrIcon = jest.fn();

jest.mock("@/icons/vLLM", () => ({
  VllmIcon: mockVllmIcon,
}));

jest.mock("@/icons/OpenRAG", () => ({
  OpenRAGIcon: mockOpenRAGIcon,
}));

jest.mock("@/icons/Figranium", () => ({
  FigraniumIcon: mockFigraniumIcon,
}));

jest.mock("@/icons/Keenable", () => ({
  KeenableIcon: mockKeenableIcon,
}));

jest.mock("@/icons/Piloterr", () => ({
  PiloterrIcon: mockPiloterrIcon,
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

  it("loads the Keenable bundle icon", async () => {
    const { default: icon } = await lazyIconsMapping.Keenable();

    expect(icon).toBe(mockKeenableIcon);
  });

  it("loads the Piloterr bundle icon", async () => {
    const { default: icon } = await lazyIconsMapping.Piloterr();

    expect(icon).toBe(mockPiloterrIcon);
  });
});
