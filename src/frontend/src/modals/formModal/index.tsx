import { useContext, useEffect, useRef, useState } from "react";
import { FlowType } from "../../types/flow";
import { alertContext } from "../../contexts/alertContext";
import { classNames, validateNodes } from "../../utils";
import { typesContext } from "../../contexts/typesContext";
import ChatMessage from "./chatMessage";
import {
  TerminalSquare,
  MessageSquare,
  Variable,
  Eraser,
  MessageSquarePlus,
} from "lucide-react";
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
import { Label } from "../../components/ui/label";
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
import Dropdown from "../../components/dropdownComponent";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../../components/ui/dropdown-menu";
import { Button } from "../../components/ui/button";

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
  const [chatValue, setChatValue] = useState(
    tabsState[flow.id].formKeysData.input_keys[
      Object.keys(tabsState[flow.id].formKeysData.input_keys).find(
        (k) => !tabsState[flow.id].formKeysData.handle_keys.some((j) => j === k)
      )
    ]
  );
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
    message: string,
    isSend: boolean,
    thought?: string,
    files?: Array<any>
  ) => {
    setChatHistory((old) => {
      let newChat = _.cloneDeep(old);
      if (files) {
        newChat.push({ message, isSend, files, thought });
      } else if (thought) {
        newChat.push({ message, isSend, thought });
      } else {
        newChat.push({ message, isSend });
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
            files?: Array<any>;
          }) => {
            if (chatItem.message) {
              newChatHistory.push(
                chatItem.files
                  ? {
                      isSend: !chatItem.is_bot,
                      message: formatMessage(chatItem.message),
                      thought: chatItem.intermediate_steps,
                      files: chatItem.files,
                    }
                  : {
                      isSend: !chatItem.is_bot,
                      message: formatMessage(chatItem.message),
                      thought: chatItem.intermediate_steps,
                    }
              );
            }
          }
        );
        return newChatHistory;
      });
    }
    if (data.type === "start") {
      addChatHistory("", false);
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
        // make key bold
        // dangerouslySetInnerHTML={{
        //           __html: message.replace(/\n/g, "<br>"),
        //         }}
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
        const message = formatMessage(inputs);
        addChatHistory(message, true);
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
                className="h-6 w-6 text-gray-800 pl-1 dark:text-white"
                aria-hidden="true"
              />
            </DialogTitle>
            <DialogDescription>{CHAT_FORM_DIALOG_SUBTITLE}</DialogDescription>
          </DialogHeader>

          <div className="flex h-[80vh] w-full mt-2 ">
            <div className="w-2/5 h-full overflow-auto scrollbar-hide flex flex-col justify-start mr-6">
              <div className="flex py-2 items-center">
                <Variable className=" -ml-px w-4 h-4 mr-1 text-primary"></Variable>
                <span className="text-md font-semibold text-primary">
                  Input Variables
                </span>
              </div>
              <div className="flex justify-between items-center">
                <div className="flex mr-2.5 py-2 items-center">
                  <span className="text-sm font-medium text-primary">
                    Name
                  </span>
                </div>
                <div className="flex mr-2.5 py-2 items-center">
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
                          <div className="flex items-center w-full justify-between">
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
                          <div className="p-1 flex flex-col gap-2">
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
                    <div className="flex flex-1 items-center justify-between py-4 font-normal transition-all group text-muted-foreground text-sm">
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
            <div className="w-full">
              <div className="flex flex-col rounded-md border bg-muted w-full h-full relative">
                <div className="absolute right-3 top-3 z-50">
                  <button disabled={lockChat} onClick={() => clearChat()}>
                    <Eraser
                      className={classNames(
                        "h-5 w-5",
                        lockChat
                          ? "text-primary animate-pulse"
                          : "text-primary hover:text-gray-600"
                      )}
                      aria-hidden="true"
                    />
                  </button>
                </div>
                <div
                  ref={messagesRef}
                  className="w-full h-full flex-col flex items-center overflow-scroll scrollbar-hide"
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
                    <div className="flex flex-col h-full text-center justify-center w-full items-center align-middle">
                      <span>
                        👋{" "}
                        <span className="text-gray-600 dark:text-gray-300 text-lg">
                          LangFlow Chat
                        </span>
                      </span>
                      <br />
                      <div className="bg-muted dark:bg-gray-900 rounded-md w-2/4 px-6 py-8 border border-gray-200 dark:border-gray-700">
                        <span className="text-base text-gray-500">
                          Start a conversation and click the agent's thoughts{" "}
                          <span>
                            <MessageSquare className="w-5 h-5 inline animate-bounce mx-1 " />
                          </span>{" "}
                          to inspect the chaining process.
                        </span>
                      </div>
                    </div>
                  )}
                  <div ref={ref}></div>
                </div>
                <div className="w-full px-8 pb-6 flex-col flex items-center justify-between">
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
                          ] = chatValue;
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
