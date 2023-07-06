import { useContext, useEffect, useRef, useState } from "react";
import { FlowType } from "../../types/flow";
import { alertContext } from "../../contexts/alertContext";
import { classNames, validateNodes } from "../../utils";
import { typesContext } from "../../contexts/typesContext";
import ChatMessage from "./chatMessage";
import { TerminalSquare, MessageSquare, Variable, Eraser } from "lucide-react";
import { sendAllProps } from "../../types/api";
import { ChatMessageType } from "../../types/chat";
import ChatInput from "./chatInput";

import _ from "lodash";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { CHAT_FORM_DIALOG_SUBTITLE } from "../../constants";
import { TabsContext } from "../../contexts/tabsContext";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../components/ui/accordion";
import { Textarea } from "../../components/ui/textarea";
import { Badge } from "../../components/ui/badge";
import ToggleShadComponent from "../../components/toggleShadComponent";

export default function FormModal({
  flow,
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: Function;
  flow: FlowType;
}) {
  const { tabsState, setTabsState } = useContext(TabsContext);
  const [chatValue, setChatValue] = useState(() => {
    try {
      const { formKeysData } = tabsState[flow.id];
      if (!formKeysData) {
        throw new Error("formKeysData is undefined");
      }
      const inputKeys = formKeysData.input_keys;
      const handleKeys = formKeysData.handle_keys;

      const keyToUse = Object.keys(inputKeys).find(
        (k) => !handleKeys.some((j) => j === k)
      );

      return inputKeys[keyToUse];
    } catch (error) {
      console.error(error);
      // return a sensible default or `undefined` if no default is possible
      return undefined;
    }
  });

  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);
  const { reactFlowInstance } = useContext(typesContext);
  const { setErrorData, setNoticeData } = useContext(alertContext);
  const ws = useRef<WebSocket | null>(null);
  const [lockChat, setLockChat] = useState(false);
  const isOpen = useRef(open);
  const messagesRef = useRef(null);
  const id = useRef(flow.id);
  const [chatKey, setChatKey] = useState(
    Object.keys(tabsState[flow.id].formKeysData.input_keys).find(
      (k) => !tabsState[flow.id].formKeysData.handle_keys.some((j) => j === k)
    )
  );

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
  }, [flow.id, tabsState[flow.id], tabsState[flow.id].formKeysData]);

  var isStream = false;

  const addChatHistory = (
    message: string | Object,
    isSend: boolean,
    chatKey: string,
    thought?: string,
    files?: Array<any>
  ) => {
    setChatHistory((old) => {
      let newChat = _.cloneDeep(old);
      if (files) {
        newChat.push({ message, isSend, files, thought, chatKey });
      } else if (thought) {
        newChat.push({ message, isSend, thought, chatKey });
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
    end = false,
    files,
  }: {
    str?: string;
    thought?: string;
    // end param default is false
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
      return newChat;
    });
  }

  function handleOnClose(event: CloseEvent) {
    if (isOpen.current) {
      setErrorData({ title: event.reason });
      setTimeout(() => {
        connectWS();
        setLockChat(false);
      }, 1000);
    }
  }

  function getWebSocketUrl(chatId, isDevelopment = false) {
    const isSecureProtocol = window.location.protocol === "https:";
    const webSocketProtocol = isSecureProtocol ? "wss" : "ws";
    const host = isDevelopment ? "localhost:7860" : window.location.host;
    const chatEndpoint = `/api/v1/chat/${chatId}`;

    return `${
      isDevelopment ? "ws" : webSocketProtocol
    }://${host}${chatEndpoint}`;
  }

  function handleWsMessage(data: any) {
    if (Array.isArray(data)) {
      //set chat history
      setChatHistory((_) => {
        let newChatHistory: ChatMessageType[] = [];
        data.forEach(
          (chatItem: {
            intermediate_steps?: string;
            is_bot: boolean;
            message: string;
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
                      thought: chatItem.intermediate_steps,
                      files: chatItem.files,
                      chatKey: chatItem.chatKey,
                    }
                  : {
                      isSend: !chatItem.is_bot,
                      message: chatItem.message,
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
      addChatHistory("", false, chatKey);
      isStream = true;
    }
    if (data.type === "end") {
      if (data.message) {
        updateLastMessage({ str: data.message, end: true });
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
    if (data.type === "stream" && isStream) {
      updateLastMessage({ str: data.message });
    }
  }

  function connectWS() {
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
        console.log("Received data:", data);
        handleWsMessage(data);
        //get chat history
      };
      newWs.onclose = (event) => {
        handleOnClose(event);
      };
      newWs.onerror = (ev) => {
        console.log(ev, "error");
        if (flow.id === "") {
          connectWS();
        } else {
          setErrorData({
            title: "There was an error on web connection, please: ",
            list: [
              "Refresh the page",
              "Use a new flow tab",
              "Check if the backend is up",
            ],
          });
        }
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
      console.log("unmount");
      console.log(ws);
      if (ws.current) {
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
  }, [lockChat]);

  async function sendAll(data: sendAllProps) {
    try {
      if (ws) {
        ws.current.send(JSON.stringify(data));
      }
    } catch (error) {
      setErrorData({
        title: "There was an error sending the message",
        list: [error.message],
      });
      setChatValue(data.inputs);
      connectWS();
    }
  }

  useEffect(() => {
    if (ref.current) ref.current.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const ref = useRef(null);

  useEffect(() => {
    if (open && ref.current) {
      ref.current.focus();
    }
  }, [open]);
  function formatMessage(inputs: any): string {
    if (inputs) {
      if (typeof inputs == "string") return inputs;
      // inputs is a object with the keys and values being input_keys and keysValue
      // so the formated message is a string with the keys and values separated by ": "
      let message = "";
      for (const [key, value] of Object.entries(inputs)) {
        message += `<b>${key}</b>: ${value}\n`;
      }
      return message;
    }
    return "";
  }

  function sendMessage() {
    if (chatValue !== "") {
      let nodeValidationErrors = validateNodes(reactFlowInstance);
      if (nodeValidationErrors.length === 0) {
        setLockChat(true);
        let inputs = tabsState[id.current].formKeysData.input_keys;
        setChatValue("");
        const message = inputs;
        addChatHistory(message, true, chatKey);
        sendAll({
          ...reactFlowInstance.toObject(),
          inputs: inputs,
          chatHistory,
          name: flow.name,
          description: flow.description,
        });
        setTabsState((old) => {
          let newTabsState = _.cloneDeep(old);
          newTabsState[id.current].formKeysData.input_keys[chatKey] = "";
          return newTabsState;
        });
      } else {
        setErrorData({
          title: "Oops! Looks like you missed some required information:",
          list: nodeValidationErrors,
        });
      }
    } else {
      setErrorData({
        title: "Error sending message",
        list: ["The message cannot be empty."],
      });
    }
  }
  function clearChat() {
    setChatHistory([]);
    ws.current.send(JSON.stringify({ clear_history: true }));
    if (lockChat) setLockChat(false);
  }

  function setModalOpen(x: boolean) {
    setOpen(x);
  }

  function handleOnCheckedChange(checked: boolean, i: string) {
    if (checked === true) {
      setChatKey(i);
      setChatValue(tabsState[flow.id].formKeysData.input_keys[i]);
    }
  }
  return (
    <Dialog open={open} onOpenChange={setModalOpen}>
      <DialogTrigger className="hidden"></DialogTrigger>
      {tabsState[flow.id].formKeysData && (
        <DialogContent className="min-w-[80vw]">
          <DialogHeader>
            <DialogTitle className="flex items-center">
              <span className="pr-2">Chat</span>
              <TerminalSquare
                className="h-6 w-6 pl-1 text-gray-800 dark:text-white"
                aria-hidden="true"
              />
            </DialogTitle>
            <DialogDescription>{CHAT_FORM_DIALOG_SUBTITLE}</DialogDescription>
          </DialogHeader>

          <div className="mt-2 flex h-[80vh] w-full ">
            <div className="mr-6 flex h-full w-2/6 flex-col justify-start overflow-auto scrollbar-hide">
              <div className="flex items-center py-2">
                <Variable className=" -ml-px mr-1 h-4 w-4 text-primary"></Variable>
                <span className="text-md font-semibold text-primary">
                  Input Variables
                </span>
              </div>
              <div className="flex items-center justify-between pt-2">
                <div className="mr-2.5 flex items-center">
                  <span className="text-sm font-medium text-primary">Name</span>
                </div>
                <div className="mr-2.5 flex items-center">
                  <span className="text-sm font-medium text-primary">
                    Chat Input
                  </span>
                </div>
              </div>
              <Accordion type="multiple" className="w-full">
                {Object.keys(tabsState[id.current].formKeysData.input_keys).map(
                  (i, k) => (
                    <div className="flex items-start gap-3" key={k}>
                      <AccordionItem className="w-full" key={k} value={i}>
                        <AccordionTrigger className="flex gap-2">
                          <div className="flex w-full items-center justify-between">
                            <Badge variant="gray" size="md">
                              {i}
                            </Badge>

                            <div
                              className="-mb-1"
                              onClick={(event) => {
                                event.stopPropagation();
                              }}
                            >
                              <ToggleShadComponent
                                enabled={chatKey === i}
                                setEnabled={(value) =>
                                  handleOnCheckedChange(value, i)
                                }
                                size="small"
                                disabled={tabsState[
                                  id.current
                                ].formKeysData.handle_keys.some((t) => t === i)}
                              />
                            </div>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent>
                          <div className="flex flex-col gap-2 p-1">
                            {tabsState[
                              id.current
                            ].formKeysData.handle_keys.some((t) => t === i) && (
                              <div className="font-normal text-muted-foreground ">
                                Source: Component
                              </div>
                            )}
                            <Textarea
                              value={
                                tabsState[id.current].formKeysData.input_keys[i]
                              }
                              onChange={(e) => {
                                setTabsState((old) => {
                                  let newTabsState = _.cloneDeep(old);
                                  newTabsState[
                                    id.current
                                  ].formKeysData.input_keys[i] = e.target.value;
                                  return newTabsState;
                                });
                              }}
                              disabled={chatKey === i}
                              placeholder="Enter text..."
                            ></Textarea>
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    </div>
                  )
                )}
                {tabsState[id.current].formKeysData.memory_keys.map((i, k) => (
                  <AccordionItem key={k} value={i}>
                    <div className="group flex flex-1 items-center justify-between py-4 text-sm font-normal text-muted-foreground transition-all">
                      <div className="group-hover:underline">
                        <Badge size="md" variant="gray">
                          {i}
                        </Badge>
                      </div>
                      Used as Memory Key
                    </div>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
            <div className="flex w-full flex-1 flex-col">
              <div className="relative flex h-full w-full flex-col rounded-md border bg-muted">
                <div className="absolute right-3 top-3 z-50">
                  <button disabled={lockChat} onClick={() => clearChat()}>
                    <Eraser
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
                <div
                  ref={messagesRef}
                  className="flex h-full w-full flex-col items-center overflow-scroll scrollbar-hide"
                >
                  {chatHistory.length > 0 ? (
                    chatHistory.map((c, i) => (
                      <ChatMessage
                        lockChat={lockChat}
                        chat={c}
                        lastMessage={chatHistory.length - 1 == i ? true : false}
                        key={i}
                      />
                    ))
                  ) : (
                    <div className="flex h-full w-full flex-col items-center justify-center text-center align-middle">
                      <span>
                        👋{" "}
                        <span className="text-lg text-gray-600 dark:text-gray-300">
                          LangFlow Chat
                        </span>
                      </span>
                      <br />
                      <div className="w-2/4 rounded-md border border-gray-200 bg-muted px-6 py-8 dark:border-gray-700 dark:bg-gray-900">
                        <span className="text-base text-gray-500">
                          Start a conversation and click the agent's thoughts{" "}
                          <span>
                            <MessageSquare className="mx-1 inline h-5 w-5 animate-bounce " />
                          </span>{" "}
                          to inspect the chaining process.
                        </span>
                      </div>
                    </div>
                  )}
                  <div ref={ref}></div>
                </div>
                <div className="flex w-full flex-col items-center justify-between px-8 pb-6">
                  <div className="relative w-full rounded-md shadow-sm">
                    <ChatInput
                      chatValue={chatValue}
                      lockChat={lockChat}
                      sendMessage={sendMessage}
                      setChatValue={(value) => {
                        setChatValue(value);
                        setTabsState((old) => {
                          let newTabsState = _.cloneDeep(old);
                          newTabsState[id.current].formKeysData.input_keys[
                            chatKey
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
