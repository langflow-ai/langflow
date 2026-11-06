jest.unmock("react-markdown");
jest.unmock("remark-math");

import { render, screen } from "@testing-library/react";
import { SanitizedMarkdown } from "../index";

jest.mock("@/components/core/codeTabsComponent", () => () => null);
jest.mock("remark-gfm", () => () => {});

describe("chat math", () => {
  it("renders explicit double-dollar inline math", () => {
    const { container } = render(
      <SanitizedMarkdown chatMessage={"Result: $$x^2$$."} isEmpty={false} />,
    );
    expect(container.querySelector(".katex")).not.toBeNull();
    expect(container.querySelector("math")).not.toBeNull();
  });
  it("renders display equations", () => {
    const { container } = render(
      <SanitizedMarkdown
        chatMessage={"$$\n\\frac{1}{2}\n$$"}
        isEmpty={false}
      />,
    );
    expect(container.querySelector(".katex-display")).not.toBeNull();
  });
  it("leaves dollar amounts and inline code alone", () => {
    const { container } = render(
      <SanitizedMarkdown
        chatMessage={"Costs $5 and $10. `$$x$$`"}
        isEmpty={false}
      />,
    );
    expect(screen.getByText(/Costs \$5 and \$10/)).toBeInTheDocument();
    expect(container.querySelector("code")).toHaveTextContent("$$x$$");
    expect(container.querySelector(".katex")).toBeNull();
  });
  it("keeps raw HTML and TeX links untrusted", () => {
    const { container } = render(
      <SanitizedMarkdown
        chatMessage={
          '<img src="x" onerror="alert(1)"> $$\\href{javascript:alert(1)}{click}$$'
        }
        isEmpty={false}
      />,
    );
    expect(container.querySelector(".katex")).not.toBeNull();
    expect(container.querySelector(".katex a")).toBeNull();
    expect(container.querySelector("[onerror]")).toBeNull();
    expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
  });
});
