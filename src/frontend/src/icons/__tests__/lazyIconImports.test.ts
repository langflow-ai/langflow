const mockVllmIcon = jest.fn();
const mockOpenRAGIcon = jest.fn();
const mockFigraniumIcon = jest.fn();
const mockKeenableIcon = jest.fn();

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

import { render } from "@testing-library/react";
import { createElement, createRef } from "react";
import { lazyIconsMapping } from "../lazyIconImports";
import { ParallelIcon } from "../Parallel";

describe("lazyIconsMapping", () => {
  afterEach(() => jest.restoreAllMocks());

  it("loads the Parallel bundle icon", async () => {
    const { default: icon } = await lazyIconsMapping.Parallel();

    expect(icon).toBe(ParallelIcon);
  });

  it.each([false, true])(
    "renders Parallel with isDark=%s without forwarding the theme prop to SVG",
    (isDark) => {
      const consoleError = jest
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const ref = createRef<SVGSVGElement>();
      const { getByRole } = render(
        createElement(ParallelIcon, {
          isDark,
          ref,
          role: "img",
          "aria-label": "Parallel",
          className: "h-4 w-4",
        }),
      );
      const svg = getByRole("img", { name: "Parallel" });

      expect(svg).not.toHaveAttribute("isDark");
      expect(svg).toHaveClass("h-4 w-4");
      expect(ref.current).toBe(svg);
      expect(consoleError).not.toHaveBeenCalled();
    },
  );

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
});
