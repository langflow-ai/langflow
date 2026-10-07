import {
  ASSISTANT_SLASH_COMMANDS,
  detectSlashCommandQuery,
  filterSlashCommands,
} from "../slash-commands";

describe("detectSlashCommandQuery", () => {
  it("should_open_with_empty_query_when_draft_is_a_lone_slash", () => {
    expect(detectSlashCommandQuery("/", 1)).toBe("");
  });

  it("should_return_typed_command_prefix_when_caret_is_inside_the_token", () => {
    expect(detectSlashCommandQuery("/it", 3)).toBe("it");
  });

  it("should_use_only_text_before_the_caret", () => {
    expect(detectSlashCommandQuery("/iterations", 3)).toBe("it");
  });

  it("should_close_once_the_command_has_an_argument", () => {
    expect(detectSlashCommandQuery("/iterations 60", 14)).toBeNull();
  });

  it("should_ignore_a_slash_that_is_not_at_the_start_of_the_draft", () => {
    expect(detectSlashCommandQuery("build a flow /it", 16)).toBeNull();
    expect(detectSlashCommandQuery(" /it", 4)).toBeNull();
  });

  it("should_ignore_a_caret_before_the_slash", () => {
    expect(detectSlashCommandQuery("/it", 0)).toBeNull();
  });

  it("should_ignore_multiline_drafts", () => {
    expect(detectSlashCommandQuery("/it\nmore", 3)).toBeNull();
  });
});

describe("filterSlashCommands", () => {
  it("should_list_every_command_for_an_empty_query", () => {
    expect(filterSlashCommands("").map((c) => c.name)).toEqual(
      ASSISTANT_SLASH_COMMANDS.map((c) => c.name),
    );
  });

  it("should_match_command_names_by_prefix_case_insensitively", () => {
    expect(filterSlashCommands("IT").map((c) => c.name)).toEqual([
      "iterations",
    ]);
    expect(filterSlashCommands("h").map((c) => c.name)).toEqual(["history"]);
  });

  it("should_return_nothing_for_an_unknown_command", () => {
    expect(filterSlashCommands("zzz")).toEqual([]);
  });

  it("should_expose_only_commands_the_chat_hook_handles", () => {
    expect(ASSISTANT_SLASH_COMMANDS.map((c) => c.name)).toEqual([
      "skip-all",
      "history",
      "iterations",
    ]);
  });
});
