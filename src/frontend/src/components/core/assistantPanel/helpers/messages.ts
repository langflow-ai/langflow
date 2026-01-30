/**
 * Randomized messages for the assistant panel.
 * Each array contains 8 paraphrased variations with the same meaning.
 */

// Header text for the reasoning loading state
const REASONING_HEADER_MESSAGES = [
  "Reasoning...",
  "Thinking...",
  "Processing...",
  "Working on it...",
  "Analyzing...",
  "Building...",
  "Generating...",
  "Creating...",
];

// Reasoning step messages
const ANALYZING_MESSAGES = [
  "Analyzing component requirements...",
  "Understanding your component needs...",
  "Reviewing the component specifications...",
  "Processing your request details...",
  "Examining the component structure...",
  "Interpreting your requirements...",
  "Breaking down the component logic...",
  "Assessing what you need...",
];

const IDENTIFYING_INPUTS_MESSAGES = [
  "Identifying input parameters...",
  "Determining required inputs...",
  "Mapping out input fields...",
  "Defining input specifications...",
  "Setting up input parameters...",
  "Configuring the inputs...",
  "Establishing input requirements...",
  "Working out the input structure...",
];

const CHECKING_DEPENDENCIES_MESSAGES = [
  "Checking installed libraries & dependencies...",
  "Verifying available dependencies...",
  "Reviewing library requirements...",
  "Scanning for needed packages...",
  "Confirming dependency availability...",
  "Checking required libraries...",
  "Validating package dependencies...",
  "Ensuring libraries are in place...",
];

const GENERATING_CODE_MESSAGES = [
  "Generating component code...",
  "Writing the component logic...",
  "Building the component code...",
  "Crafting your component...",
  "Assembling the code structure...",
  "Creating the component implementation...",
  "Producing the component code...",
  "Constructing the component...",
];

// Validation messages
const VALIDATING_MESSAGES = [
  "Validating component...",
  "Checking component validity...",
  "Verifying the component...",
  "Running validation checks...",
  "Testing component integrity...",
  "Confirming component structure...",
  "Ensuring component is valid...",
  "Performing validation...",
];

const VALIDATION_FAILED_MESSAGES = [
  "Validation failed, analyzing errors...",
  "Found issues, reviewing errors...",
  "Validation unsuccessful, checking problems...",
  "Detected errors, analyzing...",
  "Component check failed, investigating...",
  "Issues found, examining errors...",
  "Validation error detected, reviewing...",
  "Problems found, analyzing issues...",
];

const RETRYING_MESSAGES = [
  "Retrying with fixes...",
  "Applying corrections and retrying...",
  "Making adjustments and trying again...",
  "Fixing issues and regenerating...",
  "Correcting errors and retrying...",
  "Implementing fixes...",
  "Addressing issues and retrying...",
  "Applying fixes and trying again...",
];

function getRandomMessage(messages: string[]): string {
  const index = Math.floor(Math.random() * messages.length);
  return messages[index];
}

// Generate a consistent set of messages for a single generation session
export interface ReasoningMessages {
  analyzing: string;
  identifyingInputs: string;
  checkingDependencies: string;
  generatingCode: string;
}

export interface ValidationMessages {
  validating: string;
  validationFailed: string;
  retrying: string;
}

export function getRandomReasoningMessages(): ReasoningMessages {
  return {
    analyzing: getRandomMessage(ANALYZING_MESSAGES),
    identifyingInputs: getRandomMessage(IDENTIFYING_INPUTS_MESSAGES),
    checkingDependencies: getRandomMessage(CHECKING_DEPENDENCIES_MESSAGES),
    generatingCode: getRandomMessage(GENERATING_CODE_MESSAGES),
  };
}

export function getRandomValidationMessages(): ValidationMessages {
  return {
    validating: getRandomMessage(VALIDATING_MESSAGES),
    validationFailed: getRandomMessage(VALIDATION_FAILED_MESSAGES),
    retrying: getRandomMessage(RETRYING_MESSAGES),
  };
}

export function getRandomReasoningHeader(): string {
  return getRandomMessage(REASONING_HEADER_MESSAGES);
}

export function getRandomThinkingMessage(): string {
  return getRandomMessage(REASONING_HEADER_MESSAGES);
}
