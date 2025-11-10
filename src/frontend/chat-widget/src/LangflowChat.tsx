import { useEffect } from "react";
import type { LangflowChatProps } from "./types";

export function LangflowChat({
  hostUrl,
  flowId,
  apiKey,
  title,
  chatWindowHeight,
  chatWindowWidth,
  chatTriggerStyle,
  chatPosition,
  placeholder,
  placeholderSending,
  errorMessageText,
  startOpen,
  online,
  onlineMessage,
  offlineMessage,
  botMessageStyle,
  sendButtonStyle,
  sendIconStyle,
  inputStyle,
  inputContainerStyle,
  additionalHeaders,
  ...otherProps
}: LangflowChatProps) {
  useEffect(() => {
    // Load the langflow-embedded-chat script if not already loaded
    if (!document.querySelector('script[src*="langflow-embedded-chat"]')) {
      const script = document.createElement("script");
      script.src =
        "https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js";
      script.async = true;
      document.body.appendChild(script);
    }
  }, []);

  // Convert props to web component attributes (kebab-case, string values)
  const webComponentProps: Record<string, string> = {
    host_url: hostUrl,
    flow_id: flowId,
    api_key: apiKey,
  };

  if (title) webComponentProps.window_title = title;
  if (chatWindowHeight) webComponentProps.chat_window_height = chatWindowHeight;
  if (chatWindowWidth) webComponentProps.chat_window_width = chatWindowWidth;
  if (chatTriggerStyle) webComponentProps.chat_trigger_style = chatTriggerStyle;
  if (chatPosition) webComponentProps.chat_position = chatPosition;
  if (placeholder) webComponentProps.placeholder = placeholder;
  if (placeholderSending)
    webComponentProps.placeholder_sending = placeholderSending;
  if (errorMessageText) webComponentProps.error_message_text = errorMessageText;
  if (startOpen !== undefined) webComponentProps.start_open = String(startOpen);
  if (online !== undefined) webComponentProps.online = String(online);
  if (onlineMessage) webComponentProps.online_message = onlineMessage;
  if (offlineMessage) webComponentProps.offline_message = offlineMessage;
  if (botMessageStyle) webComponentProps.bot_message_style = botMessageStyle;
  if (sendButtonStyle) webComponentProps.send_button_style = sendButtonStyle;
  if (sendIconStyle) webComponentProps.send_icon_style = sendIconStyle;
  if (inputStyle) webComponentProps.input_style = inputStyle;
  if (inputContainerStyle)
    webComponentProps.input_container_style = inputContainerStyle;
  if (additionalHeaders)
    webComponentProps.additional_headers = additionalHeaders;

  return <langflow-chat {...webComponentProps} {...otherProps} />;
}
