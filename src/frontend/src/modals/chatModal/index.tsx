import { Dialog, Transition } from "@headlessui/react";
import {
  ChatBubbleOvalLeftEllipsisIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useEffect, useRef, useState } from "react";
import { FlowType, NodeType } from "../../types/flow";
import { alertContext } from "../../contexts/alertContext";
import { toNormalCase } from "../../utils";
import { typesContext } from "../../contexts/typesContext";
import ChatMessage from "./chatMessage";
import { FaEraser } from "react-icons/fa";
import { HiX } from "react-icons/hi";
import { sendAllProps } from "../../types/api";
import { ChatMessageType, ChatType } from "../../types/chat";
import ChatInput from "./chatInput";

import _, { set } from "lodash";

export default function ChatModal({
  flow,
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: Function;
  flow: FlowType;
}) {
  const [chatValue, setChatValue] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);
  const { reactFlowInstance } = useContext(typesContext);
  const { setErrorData, setNoticeData } = useContext(alertContext);
  const ws = useRef<WebSocket | null>(null);
  const [lockChat, setLockChat] = useState(false);
  const isOpen = useRef(open);
  const messagesRef = useRef(null);
  const id = useRef(flow.id);

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
      const urlWs =
        process.env.NODE_ENV === "development"
          ? `ws://localhost:7860/api/v1/chat/${id.current}`
          : `${window.location.protocol === "https:" ? "wss" : "ws"}://${
              window.location.host
            }api/v1/chat/${id.current}`;
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
    } catch {
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
    }
  }

  useEffect(() => {
    connectWS();
    return () => {
      console.log("unmount");
      console.log(ws);
      if (ws) {
        ws.current.close();
      }
    };
  }, []);

  useEffect(() => {
    if (
      ws.current.readyState === ws.current.CLOSED ||
      ws.current.readyState === ws.current.CLOSING
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

  function validateNode(n: NodeType): Array<string> {
    if (!n.data?.node?.template || !Object.keys(n.data.node.template)) {
      setNoticeData({
        title:
          "We've noticed a potential issue with a node in the flow. Please review it and, if necessary, submit a bug report with your exported flow file. Thank you for your help!",
      });
      return [];
    }

    const {
      type,
      node: { template },
    } = n.data;

    return Object.keys(template).reduce(
      (errors: Array<string>, t) =>
        errors.concat(
          template[t].required &&
            template[t].show &&
            (template[t].value === undefined ||
              template[t].value === null ||
              template[t].value === "") &&
            !reactFlowInstance
              .getEdges()
              .some(
                (e) =>
                  e.targetHandle.split("|")[1] === t &&
                  e.targetHandle.split("|")[2] === n.id
              )
            ? [
                `${type} is missing ${
                  template.display_name
                    ? template.display_name
                    : toNormalCase(template[t].name)
                }.`,
              ]
            : []
        ),
      [] as string[]
    );
  }

  function validateNodes() {
    return reactFlowInstance
      .getNodes()
      .flatMap((n: NodeType) => validateNode(n));
  }

  const ref = useRef(null);

  useEffect(() => {
    if (open && ref.current) {
      ref.current.focus();
    }
  }, [open]);

  function sendMessage() {
    if (chatValue !== "") {
      let nodeValidationErrors = validateNodes();
      if (nodeValidationErrors.length === 0) {
        setLockChat(true);
        let message = chatValue;
        setChatValue("");
        addChatHistory(message, true);
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
  return (
    <Transition.Root show={open} appear={open} as={Fragment}>
      <Dialog
        as="div"
        className="relative z-10"
        onClose={setModalOpen}
        initialFocus={ref}
      >
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black backdrop-blur-sm dark:bg-gray-600 dark:bg-opacity-80 bg-opacity-80 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-10 overflow-y-auto">
          <div className="flex h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className=" drop-shadow-2xl relative flex flex-col justify-between transform h-[95%] overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-left shadow-xl transition-all w-[690px]">
                <div className="relative w-full p-4">
                  <button
                    onClick={() => clearChat()}
                    className="absolute top-2 right-10 hover:text-red-500 text-gray-600 dark:text-gray-300 dark:hover:text-red-500 z-30"
                  >
                    <FaEraser className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setModalOpen(false)}
                    className="absolute top-1.5 right-2 hover:text-red-500 text-gray-600 dark:text-gray-300 dark:hover:text-red-500 z-30"
                  >
                    <HiX className="w-5 h-5" />
                  </button>
                </div>
                <div
                  ref={messagesRef}
                  className="w-full h-full bg-white dark:bg-gray-800 border-t dark:border-t-gray-600 flex-col flex items-center overflow-scroll scrollbar-hide"
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
                      <div className="bg-gray-100 dark:bg-gray-900 rounded-md w-2/4 px-6 py-8 border border-gray-200 dark:border-gray-700">
                        <span className="text-base text-gray-500">
                          Start a conversation and click the agent’s thoughts{" "}
                          <span>
                            <ChatBubbleOvalLeftEllipsisIcon className="w-6 h-6 inline animate-bounce " />
                          </span>{" "}
                          to inspect the chaining process.
                        </span>
                      </div>
                    </div>
                  )}
                  <div ref={ref}></div>
                </div>
                <div className="w-full bg-white dark:bg-gray-800 border-t dark:border-t-gray-600 flex-col flex items-center justify-between p-3">
                  <div className="relative w-full  mt-1 rounded-md shadow-sm">
                    <ChatInput
                      chatValue={chatValue}
                      lockChat={lockChat}
                      sendMessage={sendMessage}
                      setChatValue={setChatValue}
                      inputRef={ref}
                    />
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
}
