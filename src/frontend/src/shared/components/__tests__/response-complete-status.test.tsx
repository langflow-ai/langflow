import { render, screen } from "@testing-library/react";
import { ResponseCompleteStatus } from "../response-complete-status";

// Safari/VoiceOver drops announcements when a live region's child element is
// remounted with identical text (LE-2041 QA). The status region must instead
// mutate one persistent text node, with consecutive completions still
// producing a text change.
describe("ResponseCompleteStatus", () => {
  it("should_stay_silent_before_the_first_completion", () => {
    render(<ResponseCompleteStatus completedCount={0} />);

    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("should_announce_via_a_direct_text_node_without_wrapper_elements", () => {
    render(<ResponseCompleteStatus completedCount={1} />);

    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Response complete");
    expect(status.children).toHaveLength(0);
  });

  it("should_mutate_the_same_text_node_across_completions", () => {
    const { rerender } = render(<ResponseCompleteStatus completedCount={1} />);
    const status = screen.getByRole("status");
    const textNode = status.firstChild;
    const firstText = status.textContent;

    rerender(<ResponseCompleteStatus completedCount={2} />);

    expect(status.firstChild).toBe(textNode);
    expect(status.textContent).not.toBe(firstText);
    expect(status.textContent).toContain("Response complete");

    rerender(<ResponseCompleteStatus completedCount={3} />);

    expect(status.firstChild).toBe(textNode);
    expect(status.textContent).toBe(firstText);
  });
});
