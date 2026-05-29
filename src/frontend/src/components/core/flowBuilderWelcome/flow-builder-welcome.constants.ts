/**
 * UI strings for the FlowBuilderWelcome overlay. Centralized so a future
 * i18n pass can swap these out from one place without grepping the JSX.
 */

export const WELCOME_TITLE = "What do you want to build?";
/** Shown in place of WELCOME_TITLE when no model provider is configured. */
export const WELCOME_TITLE_NO_PROVIDER = "Let us set things up first";
export const WELCOME_TEXTAREA_PLACEHOLDER = "Describe your flow...";
export const WELCOME_SEND_LABEL = "Send";
export const WELCOME_SIMPLE_AGENT_LABEL = "Simple Agent";
export const WELCOME_VECTOR_STORE_RAG_LABEL = "Vector Store RAG";
export const WELCOME_BROWSE_MORE_LABEL = "Browse more...";
export const WELCOME_OR_TEMPLATE_LABEL = "Or start from a template:";

/** Cap on the typed prompt — matches the assistant chat's own textarea bound. */
export const WELCOME_MAX_INPUT_LENGTH = 500;
