import { Transition } from "@headlessui/react";
import { Fragment, useContext, useEffect, useRef, useState } from "react";
import { FlowType } from "../../types/flow";
import { alertContext } from "../../contexts/alertContext";
import { validateNodes } from "../../utils";
import { typesContext } from "../../contexts/typesContext";
import ChatMessage from "./chatMessage";
import { X, MessagesSquare, Eraser, TerminalSquare } from "lucide-react";
import { sendAllProps } from "../../types/api";
import { ChatMessageType } from "../../types/chat";
import ChatInput from "./chatInput";

import _ from "lodash";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { dark } from "@mui/material/styles/createPalette";
import { CODE_PROMPT_DIALOG_SUBTITLE } from "../../constants";
import { postValidateCode } from "../../controllers/API";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { TabsContext } from "../../contexts/tabsContext";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../components/ui/accordion";
import { AccordionHeader } from "@radix-ui/react-accordion";
import { Textarea } from "../../components/ui/textarea";
import { Badge } from "../../components/ui/badge";
import { Separator } from "../../components/ui/separator";
import { Switch } from "../../components/ui/switch";

export default function FormModal({
  flow,
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: Function;
  flow: FlowType;
}) {
  const [chatValue, setChatValue] = useState("");
  const [keysValue, setKeysValue] = useState([]);
  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);
  const { reactFlowInstance } = useContext(typesContext);
  const { setErrorData, setNoticeData } = useContext(alertContext);
  const { tabsState } = useContext(TabsContext);
  const ws = useRef<WebSocket | null>(null);
  const [lockChat, setLockChat] = useState(false);
  const isOpen = useRef(open);
  const messagesRef = useRef(null);
  const id = useRef(flow.id);
  const [chatKey, setChatKey] = useState(0);

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
    setKeysValue(Array(tabsState[flow.id].formKeysData.input_keys.length).fill(""));
  }, [flow.id]);

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
            intermediate_steps?: "string";
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
                      message: chatItem.message,
                      thought: chatItem.intermediate_steps,
                      files: chatItem.files,
                    }
                  : {
                      isSend: !chatItem.is_bot,
                      message: chatItem.message,
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
      setChatValue(data.message);
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

  function sendMessage() {
    if (chatValue !== "") {
      let nodeValidationErrors = validateNodes(reactFlowInstance);
      if (nodeValidationErrors.length === 0) {
        setLockChat(true);
        // Message variable makes a object with the keys being the names from tabsState[flow.id].formKeysData.input_keys and the values being the keysValue of the correspondent index
        let keys = tabsState[flow.id].formKeysData.input_keys; // array of keys
        let values = keysValue.map((k, i) => i == chatKey ? chatValue : k); // array of values
        let message = keys.reduce((object, key, index) => {
          object[key] = values[index];
          return object;
        }, {});
        setChatValue("");
        addChatHistory(message.toString(), true);
        sendAll({
          ...reactFlowInstance.toObject(),
          message,
          chatHistory,
          name: flow.name,
          description: flow.description,
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

  function handleOnCheckedChange(checked: boolean, index: number) {
    if(checked === true){
      setChatKey(index);
    }
  }
  return (
    <Dialog open={open} onOpenChange={setModalOpen}>
      <DialogTrigger className="hidden"></DialogTrigger>
      <DialogContent className="min-w-[95vw]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">Chat Form</span>
            <TerminalSquare
              className="h-6 w-6 text-gray-800 pl-1 dark:text-white"
              aria-hidden="true"
            />
          </DialogTitle>
        </DialogHeader>

        <div className="flex h-[80vh] w-full mt-2">
          <div className="w-2/5 h-full flex flex-col justify-start mr-6">
            <Accordion type="single" collapsible className="w-full">
              {tabsState[id.current].formKeysData.input_keys.map((i, k) => (
                <AccordionItem key={k} value={i}>
                  <AccordionTrigger>{i}</AccordionTrigger>
                  <AccordionContent>
                    <div className="p-1 flex flex-col gap-4">
                    <div className="flex items-center space-x-2">
                      <Switch id="airplane-mode" checked={chatKey === k } onCheckedChange={(value) => handleOnCheckedChange(value, k)}/>
                      <Label htmlFor="airplane-mode">From Chat</Label>
                    </div>
                      <Textarea value={keysValue[k]} onChange={(e) => setKeysValue({...keysValue, [k]: e.target.value})} disabled={chatKey === k} placeholder="Enter text..."></Textarea>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
              {tabsState[id.current].formKeysData.memory_keys.map((i, k) => (
                <AccordionItem key={k} value={i}>
                  <div className="flex flex-1 items-center justify-between py-4 font-medium transition-all group">
                    <div className="group-hover:underline">{i}</div>
                    <Badge>Memory Key</Badge>
                  </div>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
          <div className="w-full ">
            <div className="flex flex-col rounded-md border bg-muted w-full h-full">
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
                        Start a conversation and click the agent’s thoughts{" "}
                        <span>
                          <MessagesSquare className="w-5 h-5 inline animate-bounce mx-1 " />
                        </span>{" "}
                        to inspect the chaining process.
                      </span>
                    </div>
                  </div>
                )}
                <div ref={ref}></div>
              </div>
              <div className="w-full p-2 flex-col flex items-center justify-between">
                <div className="relative w-full rounded-md shadow-sm">
                  <ChatInput
                    chatValue={chatValue}
                    lockChat={lockChat}
                    sendMessage={sendMessage}
                    setChatValue={setChatValue}
                    inputRef={ref}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
