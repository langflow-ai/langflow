jest.unmock("react-markdown");
jest.mock("remark-gfm", () => () => {});

import { fireEvent, render, screen } from "@testing-library/react";
import { ReportMarkdown, reportCitations } from "../components/report-markdown";

it("preserves reference order and transforms citations inside styled text, leaving code literal", () => {
  const select = jest.fn();
  const markdown =
    "**Claim [@alpha]** and repeated [@alpha].\n\n`[@beta]`\n\nSecond [@beta]";
  expect(reportCitations(markdown)).toEqual(["alpha", "beta"]);
  render(<ReportMarkdown markdown={markdown} onCitation={select} />);
  expect(
    screen.getAllByRole("button", { name: "Inspect source 1" }),
  ).toHaveLength(2);
  expect(
    screen.getAllByRole("button", { name: "Inspect source 2" }),
  ).toHaveLength(1);
  expect(screen.getByText("[@beta]").tagName).toBe("CODE");
  fireEvent.click(screen.getByRole("button", { name: "Inspect source 2" }));
  expect(select).toHaveBeenCalledWith("beta");
});

it("does not execute raw HTML, load remote images, or link to unsafe schemes", () => {
  const { container } = render(
    <ReportMarkdown
      onCitation={() => {}}
      markdown={
        '<script>alert(1)</script>\n\n<img src="https://tracker.test/pixel">\n\n![chart](https://tracker.test/image)\n\n[Bad](javascript:alert%281%29) and [Good](https://example.com)'
      }
    />,
  );
  expect(container.querySelector("script, img")).toBeNull();
  expect(screen.queryByRole("link", { name: "Bad" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Good" })).toHaveAttribute(
    "rel",
    "noopener noreferrer",
  );
});
