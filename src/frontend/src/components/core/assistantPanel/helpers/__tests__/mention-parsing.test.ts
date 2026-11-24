import {
  detectFieldMention,
  detectMention,
  formatFieldMentionToken,
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
  it("should_wrap_id_in_single_quotes_without_trailing_space", () => {
    expect(formatMentionToken("ChatInput-abc12")).toBe("'ChatInput-abc12'");
  });
});

describe("detectFieldMention", () => {
  it("should_detect_field_query_right_after_a_component_token", () => {
    const value = "'ChatInput-abc'.inp";
    expect(detectFieldMention(value, value.length)).toEqual({
      start: 0,
      componentId: "ChatInput-abc",
      query: "inp",
    });
  });

  it("should_detect_with_empty_query_when_dot_just_typed", () => {
    const value = "'Node-1'.";
    expect(detectFieldMention(value, value.length)).toEqual({
      start: 0,
      componentId: "Node-1",
      query: "",
    });
  });

  it("should_detect_token_mid_sentence_after_whitespace", () => {
    const value = "use 'OpenAI-x'.temp";
    expect(detectFieldMention(value, value.length)).toEqual({
      start: 4,
      componentId: "OpenAI-x",
      query: "temp",
    });
  });

  it("should_return_null_when_whitespace_in_field_query", () => {
    const value = "'Node-1'.in put";
    expect(detectFieldMention(value, value.length)).toBeNull();
  });

  it("should_return_null_when_dot_not_adjacent_to_a_token", () => {
    expect(detectFieldMention("plain.field", 11)).toBeNull();
  });

  it("should_return_null_for_a_bare_component_token", () => {
    const value = "'Node-1'";
    expect(detectFieldMention(value, value.length)).toBeNull();
  });
});

describe("formatFieldMentionToken", () => {
  it("should_wrap_id_and_field_as_one_terminal_token", () => {
    expect(formatFieldMentionToken("ChatInput-abc", "input_value")).toBe(
      "'ChatInput-abc.input_value' ",
    );
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
