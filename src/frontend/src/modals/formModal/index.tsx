import { useContext, useEffect, useRef, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { typesContext } from "../../contexts/typesContext";
import { sendAllProps } from "../../types/api";
import { ChatMessageType } from "../../types/chat";
import { FlowType } from "../../types/flow";
import { classNames } from "../../utils/utils";
import ChatInput from "./chatInput";
import ChatMessage from "./chatMessage";

import _ from "lodash";
import AccordionComponent from "../../components/AccordionComponent";
import IconComponent from "../../components/genericIconComponent";
import ToggleShadComponent from "../../components/toggleShadComponent";
import { Badge } from "../../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { Textarea } from "../../components/ui/textarea";
import { CHAT_FORM_DIALOG_SUBTITLE } from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import { FlowsContext } from "../../contexts/flowsContext";
import { getBuildStatus } from "../../controllers/API";
import { FlowsState } from "../../types/tabs";
import { validateNodes } from "../../utils/reactflowUtils";

export default function FormModal({
  flow,
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
  flow: FlowType;
}): JSX.Element {
  const { tabsState, setTabsState } = useContext(FlowsContext);
  const [chatValue, setChatValue] = useState(() => {
    try {
      const { formKeysData } = tabsState[flow.id];
      if (!formKeysData) {
        throw new Error("formKeysData is undefined");
      }
      const inputKeys = formKeysData.input_keys;
      const handleKeys = formKeysData.handle_keys;

      const keyToUse = Object.keys(inputKeys!).find(
        (key) => !handleKeys?.some((j) => j === key) && inputKeys![key] === ""
      );

      return inputKeys![keyToUse!];
    } catch (error) {
      console.error(error);
      // return a sensible default or `undefined` if no default is possible
      return undefined;
    }
  });

  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);
  const template = useRef(tabsState[flow.id].formKeysData.template);
  const { reactFlowInstance } = useContext(typesContext);
  const { accessToken } = useContext(AuthContext);
  const { setErrorData } = useContext(alertContext);
  const ws = useRef<WebSocket | null>(null);
  const [lockChat, setLockChat] = useState(false);
  const isOpen = useRef(open);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const id = useRef(flow.id);
  const tabsStateFlowId = tabsState[flow.id];
  const tabsStateFlowIdFormKeysData = tabsStateFlowId.formKeysData;
  const [chatKey, setChatKey] = useState(() => {
    if (tabsState[flow.id]?.formKeysData?.input_keys) {
      return Object.keys(tabsState[flow.id].formKeysData.input_keys!).find(
        (key) =>
          !tabsState[flow.id].formKeysData.handle_keys!.some(
            (j) => j === key
          ) && tabsState[flow.id].formKeysData.input_keys![key] === ""
      );
    }
    // TODO: return a sensible default
    return "";
  });
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [chatHistory]);

  useEffect(() => {
    isOpen.current = open;
  }, [open]);
  useEffect(() => {
    id.current = flow.id;
  }, [flow.id, tabsStateFlowId, tabsStateFlowIdFormKeysData]);

  var isStream = false;

  const addChatHistory = (
    message: string | Object,
    isSend: boolean,
    chatKey: string,
    template?: string,
    thought?: string,
    files?: Array<any>
  ) => {
    setChatHistory((old) => {
      let newChat = _.cloneDeep(old);
      if (files) {
        newChat.push({ message, isSend, files, thought, chatKey });
      } else if (thought) {
        newChat.push({ message, isSend, thought, chatKey });
      } else if (template) {
        newChat.push({ message, isSend, chatKey, template });
      } else {
        newChat.push({ message, isSend, chatKey });
      }
      return newChat;
    });
  };
  //add proper type signature for function

  function updateLastMessage({
    str,
    thought,
    prompt,
    end = false,
    files,
  }: {
    str?: string;
    thought?: string;
    prompt?: string;
    end?: boolean;
    files?: Array<any>;
  }) {
    setChatHistory((old) => {
      let newChat = [...old];
      if (str) {
        if (end) {
          newChat[newChat.length - 1].message = str;
        } else {
          newChat[newChat.length - 1].message =
            newChat[newChat.length - 1].message + str;
        }
      }
      if (thought) {
        newChat[newChat.length - 1].thought = thought;
      }
      if (files) {
        newChat[newChat.length - 1].files = files;
      }
      if (prompt) {
        newChat[newChat.length - 2].template = prompt;
      }
      return newChat;
    });
  }

  function handleOnClose(event: CloseEvent): void {
    if (isOpen.current) {
      //check if the user has been logged out, if so close the chat when the user is redirected to the login page
      if (window.location.href.includes("login")) {
        setOpen(false);
        ws.current?.close();
        return;
      }

      getBuildStatus(flow.id)
        .then((response) => {
          if (response.data.built) {
            connectWS();
          } else {
            setErrorData({
              title: "Please build the flow again before using the chat.",
            });
          }
        })
        .catch((error) => {
          setErrorData({
            title: error.data?.detail ? error.data.detail : error.message,
          });
        });
      setErrorData({ title: event.reason });
      setTimeout(() => {
        setLockChat(false);
      }, 1000);
    }
  }
  //TODO improve check of user authentication
  function getWebSocketUrl(
    chatId: string,
    isDevelopment: boolean = false
  ): string {
    const isSecureProtocol =
      window.location.protocol === "https:" || window.location.port === "443";
    const webSocketProtocol = isSecureProtocol ? "wss" : "ws";
    const host = isDevelopment ? "localhost:7860" : window.location.host;

    const chatEndpoint = `/api/v1/chat/${chatId}`;

    return `${
      isDevelopment ? "ws" : webSocketProtocol
    }://${host}${chatEndpoint}?token=${encodeURIComponent(accessToken!)}`;
  }

  function handleWsMessage(data: any) {
    if (Array.isArray(data) && data.length > 0) {
      //set chat history
      setChatHistory((_) => {
        console.log(data);
        let newChatHistory: ChatMessageType[] = [];
        for (let i = 0; i < data.length; i++) {
          if (data[i].type === "prompt" && data[i].prompt) {
            if (data[i - 1] && !data[i - 1].is_bot) {
              data[i - 1].prompt = data[i].prompt;
              template.current = data[i].prompt;
            }
          }
        }
        data = data.filter((item: any) => item.type !== "prompt");
        data.forEach(
          (chatItem: {
            intermediate_steps?: string;
            is_bot: boolean;
            message: string;
            prompt?: string;
            type: string;
            chatKey: string;
            files?: Array<any>;
          }) => {
            if (chatItem.message) {
              newChatHistory.push(
                chatItem.files
                  ? {
                      isSend: !chatItem.is_bot,
                      message: chatItem.message,
                      template: chatItem.prompt,
                      thought: chatItem.intermediate_steps,
                      files: chatItem.files,
                      chatKey: chatItem.chatKey,
                    }
                  : {
                      isSend: !chatItem.is_bot,
                      message: chatItem.message,
                      template: chatItem.prompt,
                      thought: chatItem.intermediate_steps,
                      chatKey: chatItem.chatKey,
                    }
              );
            }
          }
        );
        return newChatHistory;
      });
    }
    if (data.type === "start") {
      addChatHistory("", false, chatKey!);
      isStream = true;
    }
    if (data.type === "end") {
      if (data.message) {
        updateLastMessage({
          str: data.message,
          end: true,
          prompt: template.current,
        });
      }
      if (data.intermediate_steps) {
        updateLastMessage({
          str: data.message,
          thought: data.intermediate_steps,
          end: true,
        });
      }
      if (data.files) {
        updateLastMessage({
          end: true,
          files: data.files,
        });
      }
      setLockChat(false);
      isStream = false;
    }
    if (data.type == "prompt" && data.prompt) {
      template.current = data.prompt;
    }
    if (data.type === "stream" && isStream) {
      updateLastMessage({ str: data.message });
    }
  }

  function connectWS(): void {
    try {
      const urlWs = getWebSocketUrl(
        id.current,
        process.env.NODE_ENV === "development"
      );
      const newWs = new WebSocket(urlWs);
      newWs.onopen = () => {
        console.log("WebSocket connection established!");
      };
      newWs.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWsMessage(data);
        //get chat history
      };
      newWs.onclose = (event) => {
        handleOnClose(event);
      };
      newWs.onerror = (ev) => {
        console.log(ev);
        connectWS();
      };
      ws.current = newWs;
    } catch (error) {
      if (flow.id === "") {
        connectWS();
      }
      console.log(error);
    }
  }

  useEffect(() => {
    connectWS();
    return () => {
      console.log(ws);
      if (ws.current) {
        ws.current.close();
      }
    };
    // do not add connectWS on dependencies array
  }, [open]);

  useEffect(() => {
    return () => {
      if (ws.current) {
        console.log("closing ws");
        ws.current.close();
      }
    };
  }, []);

  useEffect(() => {
    if (
      ws.current &&
      (ws.current.readyState === ws.current.CLOSED ||
        ws.current.readyState === ws.current.CLOSING)
    ) {
      connectWS();
      setLockChat(false);
    }
    // do not add connectWS on dependencies array
  }, [lockChat]);

  async function sendAll(data: sendAllProps): Promise<void> {
    try {
      if (ws) {
        ws.current?.send(JSON.stringify(data));
      }
    } catch (error) {
      setErrorData({
        title: "There was an error sending the message",
        list: [(error as { message: string }).message],
      });
      setChatValue(data.inputs);
      connectWS();
    }
  }

  useEffect(() => {
    if (ref.current) ref.current.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (open && ref.current) {
      ref.current.focus();
    }
  }, [open]);

  function sendMessage(): void {
    let nodeValidationErrors = validateNodes(
      reactFlowInstance!.getNodes(),
      reactFlowInstance!.getEdges()
    );
    if (nodeValidationErrors.length === 0) {
      setLockChat(true);
      let inputs = tabsState[id.current].formKeysData.input_keys;
      setChatValue("");
      const message = inputs;
      addChatHistory(message!, true, chatKey!, template.current);
      sendAll({
        ...flow.data!,
        inputs: inputs!,
        chatHistory,
        name: flow.name,
        description: flow.description,
        chatKey: chatKey!,
      });
      //@ts-ignore
      setTabsState((old: FlowsState) => {
        if (!chatKey) return old;
        let newTabsState = _.cloneDeep(old);
        newTabsState[id.current].formKeysData.input_keys![chatKey] = "";
        return newTabsState;
      });
    } else {
      setErrorData({
        title: "Oops! Looks like you missed some required information:",
        list: nodeValidationErrors,
      });
    }
  }
  function clearChat(): void {
    setChatHistory([]);
    template.current = tabsState[id.current].formKeysData.template;
    ws.current?.send(JSON.stringify({ clear_history: true }));
    if (lockChat) setLockChat(false);
  }

  function handleOnCheckedChange(checked: boolean, i: string) {
    if (checked === true) {
      setChatKey(i);
      setChatValue(tabsState[flow.id].formKeysData.input_keys![i]);
    } else {
      setChatKey(null!);
      setChatValue("");
    }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger hidden></DialogTrigger>
      {tabsState[flow.id].formKeysData && (
        <DialogContent className="min-w-[80vw]">
          <DialogHeader>
            <DialogTitle className="flex items-center">
              <span className="pr-2">Chat</span>
              <IconComponent
                name="prompts"
                className="h-6 w-6 pl-1 text-foreground"
                aria-hidden="true"
              />
            </DialogTitle>
            <DialogDescription>{CHAT_FORM_DIALOG_SUBTITLE}</DialogDescription>
          </DialogHeader>

          <div className="form-modal-iv-box ">
            <div className="form-modal-iv-size">
              <div className="file-component-arrangement">
                <IconComponent
                  name="Variable"
                  className=" file-component-variable"
                />
                <span className="file-component-variables-span text-md">
                  Input Variables
                </span>
              </div>
              <div className="file-component-variables-title">
                <div className="file-component-variables-div">
                  <span className="text-sm font-medium text-primary">Name</span>
                </div>
                <div className="file-component-variables-div">
                  <span className="text-sm font-medium text-primary">
                    Chat Input
                  </span>
                </div>
              </div>

              {tabsState[id.current]?.formKeysData?.input_keys
                ? Object.keys(
                    tabsState[id.current].formKeysData.input_keys!
                  ).map((key, index) => (
                    <div className="file-component-accordion-div" key={index}>
                      <AccordionComponent
                        trigger={
                          <div className="file-component-badge-div">
                            <Badge variant="gray" size="md">
                              {key}
                            </Badge>

                            <div
                              className="-mb-1"
                              onClick={(event) => {
                                event.stopPropagation();
                              }}
                            >
                              <ToggleShadComponent
                                enabled={chatKey === key}
                                setEnabled={(value) =>
                                  handleOnCheckedChange(value, key)
                                }
                                size="small"
                                disabled={tabsState[
                                  id.current
                                ].formKeysData.handle_keys!.some(
                                  (t) => t === key
                                )}
                              />
                            </div>
                          </div>
                        }
                        key={index}
                        keyValue={key}
                      >
                        <div className="file-component-tab-column">
                          {tabsState[id.current].formKeysData.handle_keys!.some(
                            (t) => t === key
                          ) && (
                            <div className="font-normal text-muted-foreground ">
                              Source: Component
                            </div>
                          )}
                          <Textarea
                            className="custom-scroll"
                            value={
                              tabsState[id.current].formKeysData.input_keys![
                                key
                              ]
                            }
                            onChange={(e) => {
                              //@ts-ignore
                              setTabsState((old: FlowsState) => {
                                let newTabsState = _.cloneDeep(old);
                                newTabsState[
                                  id.current
                                ].formKeysData.input_keys![key] =
                                  e.target.value;
                                return newTabsState;
                              });
                            }}
                            disabled={chatKey === key}
                            placeholder="Enter text..."
                          ></Textarea>
                        </div>
                      </AccordionComponent>
                    </div>
                  ))
                : null}
              {tabsState[id.current].formKeysData.memory_keys!.map(
                (key, index) => (
                  <div className="file-component-accordion-div" key={index}>
                    <AccordionComponent
                      trigger={
                        <div className="file-component-badge-div">
                          <Badge variant="gray" size="md">
                            {key}
                          </Badge>
                          <div className="-mb-1">
                            <ToggleShadComponent
                              enabled={chatKey === key}
                              setEnabled={() => {}}
                              size="small"
                              disabled={true}
                            />
                          </div>
                        </div>
                      }
                      key={index}
                      keyValue={key}
                    >
                      <div className="file-component-tab-column">
                        <div className="font-normal text-muted-foreground ">
                          Source: Memory
                        </div>
                      </div>
                    </AccordionComponent>
                  </div>
                )
              )}
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
                  {chatHistory.length > 0 ? (
                    chatHistory.map((chat, index) => (
                      <ChatMessage
                        lockChat={lockChat}
                        chat={chat}
                        lastMessage={
                          chatHistory.length - 1 === index ? true : false
                        }
                        key={index}
                      />
                    ))
                  ) : (
                    <div className="chat-alert-box">
                      <span>
                        👋{" "}
                        <span className="langflow-chat-span">
                          Langflow Chat
                        </span>
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
                      noInput={!chatKey}
                      lockChat={lockChat}
                      sendMessage={sendMessage}
                      setChatValue={(value) => {
                        setChatValue(value);
                        //@ts-ignore
                        setTabsState((old: FlowsState) => {
                          let newTabsState = _.cloneDeep(old);
                          newTabsState[id.current].formKeysData.input_keys![
                            chatKey!
                          ] = value;
                          return newTabsState;
                        });
                      }}
                      inputRef={ref}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </DialogContent>
      )}
    </Dialog>
  );
}
