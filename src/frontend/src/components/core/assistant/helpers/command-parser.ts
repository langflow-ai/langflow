import { HELP_TEXT, MIN_RETRIES, MAX_RETRIES_LIMIT } from "../assistant.constants";
import type { AssistantMessage } from "../assistant.types";

export type CommandResult = {
  handled: boolean;
  message?: string;
  type?: AssistantMessage["type"];
  action?: "clear";
};

export type CommandContext = {
  maxRetries: number;
  onMaxRetriesChange: (value: number) => void;
};

export const parseCommand = (
  input: string,
  context: CommandContext,
): CommandResult => {
  const trimmed = input.trim();
  const upper = trimmed.toUpperCase();

  if (upper === "HELP" || upper === "?") {
    return { handled: true, message: HELP_TEXT, type: "system" };
  }

  if (upper === "CLEAR") {
    return { handled: true, action: "clear" };
  }

  const maxRetriesMatch = trimmed.match(/^MAX_RETRIES\s*=\s*(\d+)$/i);
  if (maxRetriesMatch) {
    const value = parseInt(maxRetriesMatch[1], 10);
    if (value < MIN_RETRIES || value > MAX_RETRIES_LIMIT) {
      return {
        handled: true,
        message: `Invalid value. MAX_RETRIES must be between ${MIN_RETRIES} and ${MAX_RETRIES_LIMIT}.`,
        type: "error",
      };
    }
    context.onMaxRetriesChange(value);
    return {
      handled: true,
      message: `MAX_RETRIES set to ${value}`,
      type: "system",
    };
  }

  return { handled: false };
};
