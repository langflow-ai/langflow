import { useContext, useEffect, useRef, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { sendAllProps } from "../../types/api";
import { ChatMessageType } from "../../types/chat";
import { NodeType } from "../../types/flow";
import { classNames } from "../../utils/utils";
import ChatInput from "./chatInput";
import ChatMessage from "./chatMessage";

import { cloneDeep } from "lodash";
import IconComponent from "../../components/genericIconComponent";
import { AuthContext } from "../../contexts/authContext";
import { flowManagerContext } from "../../contexts/flowManagerContext";
import { validateNodes } from "../../utils/reactflowUtils";

export default function newChatView(): JSX.Element {
  const [chatValue, setChatValue] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);
  const {
    reactFlowInstance,
    flowPool,
    outputIds,
    inputIds,
    updateNodeFlowData,
    buildFlow,
  } = useContext(flowManagerContext);
  const { accessToken } = useContext(AuthContext);
  const { setErrorData } = useContext(alertContext);
  const [lockChat, setLockChat] = useState(false);
  const messagesRef = useRef<HTMLDivElement | null>(null);

  //build chat history
  useEffect(() => {
    outputIds.forEach((outputId) => {
      if (outputId.includes("ChatOutput")) {
        if (!flowPool[outputId] || flowPool[outputId].length === 0) return;
        let chatOutput =
          flowPool[outputId][flowPool[outputId].length - 1].results?.result ??
          "error";
        setChatHistory((prevState) => [
          ...prevState,
          { isSend: false, message: chatOutput },
        ]);
      }
    });
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

  function sendMessage(): void {
    let nodeValidationErrors = validateNodes(
      reactFlowInstance!.getNodes(),
      reactFlowInstance!.getEdges()
    );
    if (nodeValidationErrors.length === 0) {
      setLockChat(true);
      setChatValue("");
      const chatInputId = inputIds.find((inputId) =>
        inputId.includes("ChatInput")
      );
      const chatInput: NodeType = reactFlowInstance?.getNode(
        chatInputId!
      ) as NodeType;
      if (chatInput) {
        let newData = cloneDeep(chatInput.data);
        newData.node!.template["message"].value = chatValue;
        chatInput.data = { ...newData };
        updateNodeFlowData(chatInputId!, newData);
        console.log("rodou");
        buildFlow()
          .then(() => {
            setLockChat(false);
          })
          .catch((err) => {
            console.error(err);
            setLockChat(false);
          });
      }
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
    //TODO tell backend to clear chat session
    //TODO clear chat ui
    if (lockChat) setLockChat(false);
  }

  return (
    <div className="form-modal-iv-box ">
      <div className="form-modal-iv-size">
        <div className="file-component-arrangement">
          <IconComponent name="Variable" className=" file-component-variable" />
          <span className="file-component-variables-span text-md">
            Input Variables
          </span>
        </div>
        <div className="file-component-variables-title">
          <div className="file-component-variables-div">
            <span className="text-sm font-medium text-primary">Name</span>
          </div>
          <div className="file-component-variables-div">
            <span className="text-sm font-medium text-primary">Chat Input</span>
          </div>
        </div>
      </div>
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
                noInput={inputIds.includes("ChatOutput")}
                lockChat={lockChat}
                sendMessage={sendMessage}
                setChatValue={(value) => {
                  setChatValue(value);
                }}
                inputRef={ref}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
