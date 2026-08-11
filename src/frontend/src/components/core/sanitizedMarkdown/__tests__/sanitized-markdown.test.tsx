// jest.setup.js globally stubs react-markdown. This suite intentionally runs
// the real renderer, rehype-raw, and rehype-sanitize integration.
jest.unmock("react-markdown");

import { render, screen } from "@testing-library/react";
import { SanitizedMarkdown } from "../index";

// These plugins are unrelated to link rendering and keep the integration
// focused on the Markdown/raw HTML/sanitizer path.
jest.mock("@/components/core/codeTabsComponent", () => () => null);
jest.mock("rehype-mathjax/browser", () => () => {});
jest.mock("remark-gfm", () => () => {});

describe("SanitizedMarkdown", () => {
  it("pins safe attributes on sanitized raw-HTML links", () => {
    render(
      <SanitizedMarkdown
        chatMessage={
          '<a href="https://example.com/docs" target="_self" rel="opener">Docs</a>'
        }
        isEmpty={false}
      />,
    );

    const link = screen.getByRole("link", { name: "Docs" });
    expect(link).toHaveAttribute("href", "https://example.com/docs");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
