jest.unmock("react-markdown");
jest.unmock("remark-math");

import { render } from "@testing-library/react";
import ContentDisplay from "../ContentDisplay";
import { ToolOutputDisplay } from "../ToolOutputDisplay";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: () => null,
}));
jest.mock("@/components/core/codeTabsComponent", () => ({
  __esModule: true,
  default: ({ code }: { code: string }) => <pre>{code}</pre>,
}));
jest.mock("../DurationDisplay", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("remark-gfm", () => () => {});
const renderers = {
  content: (text: string) => (
    <ContentDisplay content={{ type: "text", text }} chatId="math-test" />
  ),
  tool: (text: string) => <ToolOutputDisplay output={text} />,
};
for (const [name, renderer] of Object.entries(renderers)) {
  describe(`${name} math pipeline`, () => {
    it("renders inline and display equations", () => {
      const { container } = render(
        renderer("Result: $$x^2$$.\n\n$$\n\\frac{1}{2}\n$$"),
      );
      expect(container.querySelectorAll(".katex")).toHaveLength(2);
      expect(container.querySelector(".katex-display")).not.toBeNull();
    });
    it("preserves currency and code", () => {
      const { container } = render(
        renderer("Costs $5 and $10. `$$x$$`\n\n```text\n$$y$$\n```"),
      );
      expect(container).toHaveTextContent("Costs $5 and $10.");
      expect(container.querySelector("code")).toHaveTextContent("$$x$$");
      expect(container).toHaveTextContent("$$y$$");
      expect(container.querySelector(".katex")).toBeNull();
    });
    it("renders math fences and rejects TeX links", () => {
      const { container } = render(
        renderer("```math\nx^2\n```\n\n$$\\href{javascript:alert(1)}{click}$$"),
      );
      expect(container.querySelector(".katex-display")).not.toBeNull();
      expect(container.querySelector(".katex a")).toBeNull();
    });
  });
}
