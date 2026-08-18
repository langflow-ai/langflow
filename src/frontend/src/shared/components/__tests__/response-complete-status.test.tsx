import { render, screen } from "@testing-library/react";
import {
  ResponseCompleteStatus,
  stripMarkdownForSpeech,
} from "../response-complete-status";

// The muted transcript makes this status region the reply's only path to the
// screen reader: it must announce the reply content (LE-2041 QA), through one
// persistent text node — Safari/VoiceOver drops announcements when a live
// region's child element is remounted with identical text.
describe("ResponseCompleteStatus", () => {
  it("should_stay_silent_before_the_first_completion", () => {
    render(
      <ResponseCompleteStatus completedCount={0} completedText="ignored" />,
    );

    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("should_announce_the_reply_text_via_a_direct_text_node", () => {
    render(
      <ResponseCompleteStatus
        completedCount={1}
        completedText="The answer is 42."
      />,
    );

    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("The answer is 42.");
    expect(status.children).toHaveLength(0);
  });

  it("should_fall_back_to_the_generic_cue_for_non_text_replies", () => {
    render(<ResponseCompleteStatus completedCount={1} completedText="" />);

    expect(screen.getByRole("status")).toHaveTextContent("Response complete");
  });

  it("should_empty_the_region_once_the_announcement_is_retired", () => {
    const { rerender } = render(
      <ResponseCompleteStatus
        completedCount={1}
        completedText="The answer is 42."
        isAnnouncing
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("The answer is 42.");

    rerender(
      <ResponseCompleteStatus
        completedCount={1}
        completedText=""
        isAnnouncing={false}
      />,
    );

    // Not the generic cue — a retired announcement must be silent, otherwise
    // clearing it would speak a second time.
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("should_strip_markdown_syntax_from_the_announcement", () => {
    render(
      <ResponseCompleteStatus
        completedCount={1}
        completedText={"# Result\nUse **bold** and `code` [here](https://x.y)."}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Result Use bold and code here.",
    );
  });

  it("should_mutate_the_same_text_node_across_completions", () => {
    const { rerender } = render(
      <ResponseCompleteStatus completedCount={1} completedText="same reply" />,
    );
    const status = screen.getByRole("status");
    const textNode = status.firstChild;
    const firstText = status.textContent;

    rerender(
      <ResponseCompleteStatus completedCount={2} completedText="same reply" />,
    );

    expect(status.firstChild).toBe(textNode);
    expect(status.textContent).not.toBe(firstText);
    expect(status.textContent).toContain("same reply");

    rerender(
      <ResponseCompleteStatus completedCount={3} completedText="same reply" />,
    );

    expect(status.firstChild).toBe(textNode);
    expect(status.textContent).toBe(firstText);
  });
});

describe("stripMarkdownForSpeech", () => {
  it("should_keep_code_fence_content_but_drop_the_fences", () => {
    expect(stripMarkdownForSpeech("```python\nprint(1)\n```")).toBe("print(1)");
  });

  it("should_flatten_images_and_links_to_their_text", () => {
    expect(stripMarkdownForSpeech("![chart](img.png) see [docs](u)")).toBe(
      "chart see docs",
    );
  });
});
