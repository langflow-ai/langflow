export interface AssistantSlashCommand {
  /** Command name without the leading slash; matches what `useAssistantChat` parses. */
  name: string;
  /** Argument syntax shown next to the name; empty for commands that take none. */
  argumentHint: string;
  descriptionKey: string;
}

export const ASSISTANT_SLASH_COMMANDS: readonly AssistantSlashCommand[] = [
  {
    name: "skip-all",
    argumentHint: "",
    descriptionKey: "assistant.slashCommands.skipAllDescription",
  },
  {
    name: "history",
    argumentHint: "[N | off]",
    descriptionKey: "assistant.slashCommands.historyDescription",
  },
  {
    name: "iterations",
    argumentHint: "[N | off]",
    descriptionKey: "assistant.slashCommands.iterationsDescription",
  },
];

const COMMAND_TOKEN_BEFORE_CARET = /^\/([\w-]*)$/;

/**
 * Return the command prefix being typed, or null when the menu should stay closed.
 * Only a draft that starts with "/" and whose caret is still inside that first token
 * counts, so a slash in a prompt ("use a/b") or a typed argument never reopens it.
 */
export function detectSlashCommandQuery(
  value: string,
  caret: number,
): string | null {
  if (value.includes("\n")) return null;
  const match = COMMAND_TOKEN_BEFORE_CARET.exec(value.slice(0, caret));
  return match ? match[1] : null;
}

export function filterSlashCommands(query: string): AssistantSlashCommand[] {
  const normalized = query.toLowerCase();
  return ASSISTANT_SLASH_COMMANDS.filter((command) =>
    command.name.startsWith(normalized),
  );
}
