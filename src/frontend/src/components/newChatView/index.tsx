import { cloneDeep } from "lodash";
import { useEffect, useRef, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
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

export default function newChatView(): JSX.Element {
  const [chatValue, setChatValue] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);
  const {
    flowPool,
    outputIds,
    inputIds,
    inputTypes,
    getNode,
    setNode,
    buildFlow,
    getFlow,
    CleanFlowPool,
  } = useFlowStore();
  const { setErrorData } = useAlertStore();
  const [lockChat, setLockChat] = useState(false);
  const messagesRef = useRef<HTMLDivElement | null>(null);

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
    const chatMessages: ChatMessageType[] = chatOutputResponses
      .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
      .filter((output) => !!output.data.artifacts.message)
      .map((output) => {
        const { sender, message, sender_name } = output.data
          .artifacts as ChatOutputType;
        console.log(output.data.artifacts);
        const is_ai = sender === "Machine";
        return { isSend: !is_ai, message, sender_name };
      });
    setChatHistory(chatMessages);
  }, [flowPool, outputIds]);
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [chatHistory]);

  async function sendAll(data: sendAllProps): Promise<void> {}
  useEffect(() => {
    if (ref.current) ref.current.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.focus();
    }
  }, []);

  async function sendMessage(count = 1): Promise<void> {
    const { nodes, edges } = getFlow();
    let nodeValidationErrors = validateNodes(nodes, edges);
    if (nodeValidationErrors.length === 0) {
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
        title: "Oops! Looks like you missed some required information:",
        list: nodeValidationErrors,
      });
    }
  }
  function clearChat(): void {
    setChatHistory([]);
    CleanFlowPool();
    //TODO tell backend to clear chat session
    if (lockChat) setLockChat(false);
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
                key={index}
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
