import type { HTMLAttributes } from "react";

type LangflowChatAttributeValue = string | undefined;

interface LangflowChatElementAttributes extends HTMLAttributes<HTMLElement> {
  host_url?: LangflowChatAttributeValue;
  flow_id?: LangflowChatAttributeValue;
  api_key?: LangflowChatAttributeValue;
  window_title?: LangflowChatAttributeValue;
  chat_window_height?: LangflowChatAttributeValue;
  chat_window_width?: LangflowChatAttributeValue;
  chat_trigger_style?: LangflowChatAttributeValue;
  chat_position?: LangflowChatAttributeValue;
  placeholder?: LangflowChatAttributeValue;
  placeholder_sending?: LangflowChatAttributeValue;
  error_message_text?: LangflowChatAttributeValue;
  start_open?: LangflowChatAttributeValue;
  online?: LangflowChatAttributeValue;
  online_message?: LangflowChatAttributeValue;
  offline_message?: LangflowChatAttributeValue;
  bot_message_style?: LangflowChatAttributeValue;
  send_button_style?: LangflowChatAttributeValue;
  send_icon_style?: LangflowChatAttributeValue;
  input_style?: LangflowChatAttributeValue;
  input_container_style?: LangflowChatAttributeValue;
  additional_headers?: LangflowChatAttributeValue;
}

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "langflow-chat": LangflowChatElementAttributes;
    }
  }
}

export {};
