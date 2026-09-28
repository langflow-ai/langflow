import { MAX_HISTORY_LIMIT } from "../hooks/history-storage";
import { MAX_ITERATIONS_LIMIT } from "../hooks/iterations-storage";

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
    argumentHint: `[0–${MAX_HISTORY_LIMIT} | off]`,
    descriptionKey: "assistant.slashCommands.historyDescription",
  },
  {
    name: "iterations",
    argumentHint: `[1–${MAX_ITERATIONS_LIMIT} | off]`,
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
