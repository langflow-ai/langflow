import { useEffect, useRef, useState } from "react";
import IconComponent from "../../../../components/genericIconComponent";
import { NOCHATOUTPUT_NOTICE_ALERT } from "../../../../constants/alerts_constants";
import {
  CHAT_FIRST_INITIAL_TEXT,
  CHAT_SECOND_INITIAL_TEXT,
} from "../../../../constants/constants";
import { deleteFlowPool } from "../../../../controllers/API";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { sendAllProps } from "../../../../types/api";
import {
  ChatMessageType,
  ChatOutputType,
  FlowPoolObjectType,
} from "../../../../types/chat";
import { chatViewProps } from "../../../../types/components";
import { classNames } from "../../../../utils/utils";
import ChatInput from "./chatInput";
import ChatMessage from "./chatMessage";

export default function ChatView({
  sendMessage,
  chatValue,
  setChatValue,
  lockChat,
  setLockChat,
}: chatViewProps): JSX.Element {
  const { flowPool, outputs, inputs, CleanFlowPool } = useFlowStore();
  const { setNoticeData } = useAlertStore();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);

  const inputTypes = inputs.map((obj) => obj.type);
  const inputIds = inputs.map((obj) => obj.id);
  const outputIds = outputs.map((obj) => obj.id);
  const outputTypes = outputs.map((obj) => obj.type);
  const updateFlowPool = useFlowStore((state) => state.updateFlowPool);

  useEffect(() => {
    if (!outputTypes.includes("ChatOutput")) {
      setNoticeData({ title: NOCHATOUTPUT_NOTICE_ALERT });
    }
  }, []);

  //build chat history
  useEffect(() => {
    const chatOutputResponses: FlowPoolObjectType[] = [];
    outputIds.forEach((outputId) => {
      if (outputId.includes("ChatOutput")) {
        if (flowPool[outputId] && flowPool[outputId].length > 0) {
          chatOutputResponses.push(...flowPool[outputId]);
        }
      }
    });
    inputIds.forEach((inputId) => {
      if (inputId.includes("ChatInput")) {
        if (flowPool[inputId] && flowPool[inputId].length > 0) {
          chatOutputResponses.push(...flowPool[inputId]);
        }
      }
    });
    const chatMessages: ChatMessageType[] = chatOutputResponses
      .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
      //
      .filter((output) => output.data.artifacts?.message !== null)
      .map((output, index) => {
        try {
          const { sender, message, sender_name, stream_url } = output.data
            .artifacts as ChatOutputType;

          const is_ai = sender === "Machine" || sender === null;
          return {
            isSend: !is_ai,
            message: message,
            sender_name,
            componentId: output.id,
            stream_url: stream_url,
          };
        } catch (e) {
          console.error(e);
          return {
            isSend: false,
            message: "Error parsing message",
            sender_name: "Error",
            componentId: output.id,
          };
        }
      });
    setChatHistory(chatMessages);
  }, [flowPool]);
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, []);

  async function sendAll(data: sendAllProps): Promise<void> {}
  useEffect(() => {
    if (ref.current) ref.current.scrollIntoView({ behavior: "smooth" });
  }, []);

  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.focus();
    }
  }, []);

  function clearChat(): void {
    setChatHistory([]);
    deleteFlowPool(currentFlowId).then((_) => {
      CleanFlowPool();
    });
    //TODO tell backend to clear chat session
    if (lockChat) setLockChat(false);
  }

  function updateChat(
    chat: ChatMessageType,
    message: string,
    stream_url?: string
  ) {
    if (message === "") return;
    chat.message = message;
    // chat is one of the chatHistory
    updateFlowPool(chat.componentId, {
      message,
      sender_name: chat.sender_name ?? "Bot",
      sender: chat.isSend ? "User" : "Machine",
    });
    // setChatHistory((oldChatHistory) => {
    // const index = oldChatHistory.findIndex((ch) => ch.id === chat.id);
    // if (index === -1) return oldChatHistory;
    // let newChatHistory = _.cloneDeep(oldChatHistory);
    // newChatHistory = [
    //   ...newChatHistory.slice(0, index),
    //   chat,
    //   ...newChatHistory.slice(index + 1),
    // ];
    // console.log("newChatHistory:", newChatHistory);
    // return newChatHistory;
    // });
  }

  return (
    <div className="eraser-column-arrangement">
      <div className="eraser-size">
        <div className="eraser-position">
          <button disabled={lockChat} onClick={() => clearChat()}>
            <IconComponent
              name="Eraser"
              className={classNames(
                "h-5 w-5",
                lockChat
                  ? "animate-pulse text-primary"
                  : "text-primary hover:text-gray-600"
              )}
              aria-hidden="true"
            />
          </button>
        </div>
        <div ref={messagesRef} className="chat-message-div">
          {chatHistory?.length > 0 ? (
            chatHistory.map((chat, index) => (
              <ChatMessage
                setLockChat={setLockChat}
                lockChat={lockChat}
                chat={chat}
                lastMessage={chatHistory.length - 1 === index ? true : false}
                key={`${chat.componentId}-${index}`}
                updateChat={updateChat}
              />
            ))
          ) : (
            <div className="chat-alert-box">
              <span>
                👋 <span className="langflow-chat-span">Langflow Chat</span>
              </span>
              <br />
              <div className="langflow-chat-desc">
                <span className="langflow-chat-desc-span">
                  {CHAT_FIRST_INITIAL_TEXT}{" "}
                  <span>
                    <IconComponent
                      name="MessageSquare"
                      className="mx-1 inline h-5 w-5 animate-bounce "
                    />
                  </span>{" "}
                  {CHAT_SECOND_INITIAL_TEXT}
                </span>
              </div>
            </div>
          )}
          <div ref={ref}></div>
        </div>
        <div className="langflow-chat-input-div">
          <div className="langflow-chat-input">
            <ChatInput
              chatValue={chatValue}
              noInput={!inputTypes.includes("ChatInput")}
              lockChat={lockChat}
              sendMessage={(count) => sendMessage(count)}
              setChatValue={(value) => {
                setChatValue(value);
              }}
              inputRef={ref}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
