/**
 * Props for the LangflowChat component
 *
 * These props map to the langflow-chat web component attributes.
 * See: https://github.com/langflow-ai/langflow-embedded-chat
 */
export interface LangflowChatProps {
  /** Langflow server URL (must be HTTPS in production) */
  hostUrl: string;

  /** Flow ID or endpoint name */
  flowId: string;

  /** API key for authentication */
  apiKey: string;

  /** Chat window title (default: "Langflow Chat") */
  title?: string;

  /** Chat window height (CSS value, default: "600px") */
  chatWindowHeight?: string;

  /** Chat window width (CSS value, default: "400px") */
  chatWindowWidth?: string;

  /** Custom CSS for the chat trigger button */
  chatTriggerStyle?: string;

  /** Position of the chat widget (default: "bottom-right") */
  chatPosition?: "bottom-right" | "bottom-left" | "top-right" | "top-left";

  /** Input placeholder text */
  placeholder?: string;

  /** Placeholder text while sending */
  placeholderSending?: string;

  /** Custom error message */
  errorMessageText?: string;

  /** Start with chat window open */
  startOpen?: boolean;

  /** Online status indicator */
  online?: boolean;

  /** Message when bot is online */
  onlineMessage?: string;

  /** Message when bot is offline */
  offlineMessage?: string;

  /** Custom CSS for bot messages */
  botMessageStyle?: string;

  /** Custom CSS for send button */
  sendButtonStyle?: string;

  /** Custom CSS for send icon */
  sendIconStyle?: string;

  /** Custom CSS for input field */
  inputStyle?: string;

  /** Custom CSS for input container */
  inputContainerStyle?: string;

  /** Additional HTTP headers (JSON string) */
  additionalHeaders?: string;
}
