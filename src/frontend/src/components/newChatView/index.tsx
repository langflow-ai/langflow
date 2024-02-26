import _, { cloneDeep } from "lodash";
import { useEffect, useRef, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import { deleteFlowPool } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { sendAllProps } from "../../types/api";
import {
  ChatMessageType,
  ChatOutputType,
  FlowPoolObjectType,
} from "../../types/chat";
import { NodeType } from "../../types/flow";
import { validateNodes } from "../../utils/reactflowUtils";
import { classNames } from "../../utils/utils";
import ChatInput from "./chatInput";
import ChatMessage from "./chatMessage";
import { INFO_MISSING_ALERT, NOCHATOUTPUT_NOTICE_ALERT } from "../../alerts_constants";

export default function NewChatView(): JSX.Element {
  const [chatValue, setChatValue] = useState("");
  const {
    flowPool,
    outputs,
    inputs,
    getNode,
    setNode,
    buildFlow,
    getFlow,
    CleanFlowPool,
  } = useFlowStore();
  const { setErrorData, setNoticeData } = useAlertStore();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const [lockChat, setLockChat] = useState(false);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);

  const inputTypes = inputs.map((obj) => obj.type);
  const inputIds = inputs.map((obj) => obj.id);
  const outputIds = outputs.map((obj) => obj.id);
  const outputTypes = outputs.map((obj) => obj.type);

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

          const componentId = output.id + index;

          const is_ai = sender === "Machine" || sender === null;
          return {
            isSend: !is_ai,
            message: message,
            sender_name,
            id: componentId,
            stream_url: stream_url,
          };
        } catch (e) {
          console.error(e);
          return {
            isSend: false,
            message: "Error parsing message",
            sender_name: "Error",
            id: output.id + index,
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

  async function sendMessage(count = 1): Promise<void> {
    if (isBuilding) return;
    const { nodes, edges } = getFlow();
    let nodeValidationErrors = validateNodes(nodes, edges);
    if (nodeValidationErrors.length === 0) {
      setIsBuilding(true);
      setLockChat(true);
      setChatValue("");
      const chatInputId = inputIds.find((inputId) =>
        inputId.includes("ChatInput")
      );
      const chatInput: NodeType = getNode(chatInputId!) as NodeType;
      if (chatInput) {
        let newNode = cloneDeep(chatInput);
        newNode.data.node!.template["message"].value = chatValue;
        setNode(chatInputId!, newNode);
      }
      for (let i = 0; i < count; i++) {
        await buildFlow().catch((err) => {
          console.error(err);
          setLockChat(false);
        });
      }
      setLockChat(false);

      //set chat message in the flow and run build
      //@ts-ignore
    } else {
      setErrorData({
        title: INFO_MISSING_ALERT,
        list: nodeValidationErrors,
      });
    }
  }
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
    stream_url: string | null
  ) {
    if (message === "") return;
    console.log(`updateChat: ${message}`);
    console.log("chatHistory:", chatHistory);
    chat.message = message;
    chat.stream_url = stream_url;
    // chat is one of the chatHistory
    setChatHistory((oldChatHistory) => {
      const index = oldChatHistory.findIndex((ch) => ch.id === chat.id);

      if (index === -1) return oldChatHistory;
      let newChatHistory = _.cloneDeep(oldChatHistory);
      newChatHistory = [
        ...newChatHistory.slice(0, index),
        chat,
        ...newChatHistory.slice(index + 1),
      ];
      console.log("newChatHistory:", newChatHistory);
      return newChatHistory;
    });
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
                lockChat={lockChat}
                chat={chat}
                lastMessage={chatHistory.length - 1 === index ? true : false}
                key={`${chat.id}-${index}`}
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
                  Start a conversation and click the agent's thoughts{" "}
                  <span>
                    <IconComponent
                      name="MessageSquare"
                      className="mx-1 inline h-5 w-5 animate-bounce "
                    />
                  </span>{" "}
                  to inspect the chaining process.
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
