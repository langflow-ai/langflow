import {
  detectMention,
  formatMentionToken,
  replaceMention,
} from "../mention-parsing";

describe("detectMention", () => {
  it("should_detect_mention_when_at_is_first_char", () => {
    expect(detectMention("@", 1)).toEqual({ start: 0, query: "" });
  });

  it("should_capture_query_typed_after_at", () => {
    expect(detectMention("hi @chat", 8)).toEqual({ start: 3, query: "chat" });
  });

  it("should_return_null_when_whitespace_between_at_and_caret", () => {
    expect(detectMention("@chat input", 11)).toBeNull();
  });

  it("should_return_null_for_email_like_at_not_on_word_boundary", () => {
    expect(detectMention("user@host", 9)).toBeNull();
  });

  it("should_use_caret_not_string_end", () => {
    // Caret sits right after "@ch"; the trailing "at" is to the right.
    expect(detectMention("@chat", 3)).toEqual({ start: 0, query: "ch" });
  });

  it("should_return_null_when_no_at_present", () => {
    expect(detectMention("plain text", 10)).toBeNull();
  });

  it("should_detect_mention_after_newline_boundary", () => {
    expect(detectMention("line\n@a", 7)).toEqual({ start: 5, query: "a" });
  });
});

describe("formatMentionToken", () => {
  it("should_wrap_id_in_single_quotes_with_trailing_space", () => {
    expect(formatMentionToken("ChatInput-abc12")).toBe("'ChatInput-abc12' ");
  });
});

describe("replaceMention", () => {
  it("should_replace_the_at_query_span_with_the_token", () => {
    const result = replaceMention("ask @cha", 4, 8, "'ChatInput-x' ");
    expect(result.value).toBe("ask 'ChatInput-x' ");
    expect(result.caret).toBe(4 + "'ChatInput-x' ".length);
  });

  it("should_preserve_text_after_the_caret", () => {
    const result = replaceMention("@a rest", 0, 2, "'Node-1' ");
    expect(result.value).toBe("'Node-1'  rest");
  });
});
