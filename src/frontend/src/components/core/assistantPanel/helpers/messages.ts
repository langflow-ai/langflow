/**
 * Randomized messages for the assistant panel.
 * Each array contains 8 paraphrased variations with the same meaning.
 */
import i18n from "@/i18n";

const REASONING_HEADER_KEYS = [
  "assistant.thinking.0",
  "assistant.thinking.1",
  "assistant.thinking.2",
  "assistant.thinking.3",
  "assistant.thinking.4",
  "assistant.thinking.5",
  "assistant.thinking.6",
  "assistant.thinking.7",
];

const ANALYZING_KEYS = [
  "assistant.progress.analyzing.0",
  "assistant.progress.analyzing.1",
  "assistant.progress.analyzing.2",
  "assistant.progress.analyzing.3",
  "assistant.progress.analyzing.4",
  "assistant.progress.analyzing.5",
  "assistant.progress.analyzing.6",
  "assistant.progress.analyzing.7",
];

const IDENTIFYING_INPUTS_KEYS = [
  "assistant.progress.identifyingInputs.0",
  "assistant.progress.identifyingInputs.1",
  "assistant.progress.identifyingInputs.2",
  "assistant.progress.identifyingInputs.3",
  "assistant.progress.identifyingInputs.4",
  "assistant.progress.identifyingInputs.5",
  "assistant.progress.identifyingInputs.6",
  "assistant.progress.identifyingInputs.7",
];

const CHECKING_DEPENDENCIES_KEYS = [
  "assistant.progress.checkingDeps.0",
  "assistant.progress.checkingDeps.1",
  "assistant.progress.checkingDeps.2",
  "assistant.progress.checkingDeps.3",
  "assistant.progress.checkingDeps.4",
  "assistant.progress.checkingDeps.5",
  "assistant.progress.checkingDeps.6",
  "assistant.progress.checkingDeps.7",
];

const GENERATING_CODE_KEYS = [
  "assistant.progress.generatingCode.0",
  "assistant.progress.generatingCode.1",
  "assistant.progress.generatingCode.2",
  "assistant.progress.generatingCode.3",
  "assistant.progress.generatingCode.4",
  "assistant.progress.generatingCode.5",
  "assistant.progress.generatingCode.6",
  "assistant.progress.generatingCode.7",
];

const VALIDATING_KEYS = [
  "assistant.progress.validating.0",
  "assistant.progress.validating.1",
  "assistant.progress.validating.2",
  "assistant.progress.validating.3",
  "assistant.progress.validating.4",
  "assistant.progress.validating.5",
  "assistant.progress.validating.6",
  "assistant.progress.validating.7",
];

function getRandomMessage(keys: string[]): string {
  const key = keys[Math.floor(Math.random() * keys.length)];
  return i18n.t(key);
}

export function getRandomThinkingMessage(): string {
  return getRandomMessage(REASONING_HEADER_KEYS);
}

const PLACEHOLDER_PROGRESS_KEYS = [
  ...ANALYZING_KEYS,
  ...IDENTIFYING_INPUTS_KEYS,
  ...CHECKING_DEPENDENCIES_KEYS,
  ...GENERATING_CODE_KEYS,
  ...VALIDATING_KEYS,
];

export function getRandomPlaceholderMessage(): string {
  return getRandomMessage(PLACEHOLDER_PROGRESS_KEYS);
}
