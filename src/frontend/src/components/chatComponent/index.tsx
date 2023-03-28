import { Transition } from "@headlessui/react";
import {
	Bars3CenterLeftIcon,
	LockClosedIcon,
	PaperAirplaneIcon,
	XMarkIcon,
} from "@heroicons/react/24/outline";
import { MouseEventHandler, useContext, useEffect, useRef, useState } from "react";
import { sendAll } from "../../controllers/NodesServices";
import { alertContext } from "../../contexts/alertContext";
import { classNames, nodeColors } from "../../utils";
import { TabsContext } from "../../contexts/tabsContext";
import { ChatType } from "../../types/chat";
import ChatMessage from "./chatMessage";

const _ = require("lodash");

export default function Chat({ flow, reactFlowInstance }: ChatType) {
	const { updateFlow,lockChat,setLockChat,flows,tabIndex } = useContext(TabsContext);
	const [saveChat, setSaveChat] = useState(false);
	const [open, setOpen] = useState(true);
	const [chatValue, setChatValue] = useState("");
	const [chatHistory, setChatHistory] = useState(flow.chat);
	const { setErrorData } = useContext(alertContext);
	const addChatHistory = (
		message: string,
		isSend: boolean,
		thought?: string,
	) => {
		let tabsChange = false;
		setChatHistory((old) => {
			let newChat = _.cloneDeep(old);
			if(JSON.stringify(flow.chat) !==JSON.stringify(old)){
				tabsChange = true
				return old
			}
			if (thought) {
				newChat.push({ message, isSend, thought });
			} else {
				newChat.push({ message, isSend });
			}
			return newChat;
		});
		if(tabsChange){
			if(thought){
				updateFlow({..._.cloneDeep(flow),chat:[...flow.chat,{isSend,message,thought}]})
			}
			else{
				updateFlow({..._.cloneDeep(flow),chat:[...flow.chat,{isSend,message}]})
			}
		}
		setSaveChat((chat) => !chat);
	};
	useEffect(() => {
		updateFlow({ ..._.cloneDeep(flow), chat: chatHistory });
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [saveChat]);
	useEffect(() => {
		setChatHistory(flow.chat);
	}, [flow]);
	useEffect(() => {
		if (ref.current) ref.current.scrollIntoView({ behavior: "smooth" });
	}, [chatHistory]);
	function validateNodes() {
		if (
			reactFlowInstance
				.getNodes()
				.some(
					(n) =>
						n.data.node &&
						Object.keys(n.data.node.template).some(
							(t: any) =>
								n.data.node.template[t].required &&
								n.data.node.template[t].value === "" &&
								n.data.node.template[t].required &&
								!reactFlowInstance
									.getEdges()
									.some(
										(e) =>
											e.sourceHandle.split("|")[1] === t &&
											e.sourceHandle.split("|")[2] === n.id
									)
						)
				)
		) {
			return false;
		}
		return true;
	}
	const ref = useRef(null);

	function sendMessage() {
		if (chatValue !== "") {
			if (validateNodes()) {
				setLockChat(true);
				let message = chatValue;
				setChatValue("");
				addChatHistory(message, true);

				sendAll({ ...reactFlowInstance.toObject(), message, chatHistory,name:flow.name,description:flow.description})
					.then((r) => {
						addChatHistory(r.data.result, false, r.data.thought);
						setLockChat(false);
					})
					.catch((error) => {
						setErrorData({ title: error.message ?? "unknow error" });
						setLockChat(false);
					});
			} else {
				setErrorData({
					title: "Error sending message",
					list: [ "Oops! Looks like you missed some required information. Please fill in all the required fields before continuing."],
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
		setChatHistory([])
		updateFlow({ ..._.cloneDeep(flow), chat: []});
	}

	return (
		<>
			<Transition
				show={open}
				appear={true}
				enter="transition ease-out duration-300"
				enterFrom="translate-y-96"
				enterTo="translate-y-0"
				leave="transition ease-in duration-300"
				leaveFrom="translate-y-0"
				leaveTo="translate-y-96"
			>
				<div className="w-[340px] absolute bottom-0 right-1">
					<div className="border dark:border-gray-700 h-full rounded-xl rounded-b-none bg-white dark:bg-gray-800 shadow">
						<div
							onClick={() => {
								setOpen(false);
							}}
							className="flex justify-between cursor-pointer items-center px-5 py-2 border-b dark:border-b-gray-700"
						>
							<div className="flex gap-3 text-lg dark:text-white font-medium items-center">
								<Bars3CenterLeftIcon
									className="h-5 w-5 mt-1"
									style={{ color: nodeColors["chat"] }}
								/>
								Chat
							</div>
							<button className="hover:text-blue-500"
								onClick={(e) => {
									e.stopPropagation()
									clearChat();
								}}
							>
								Clear
							</button>
						</div>
						<div className="w-full h-[400px] flex gap-3 mb-auto overflow-y-auto scrollbar-hide flex-col bg-gray-50 dark:bg-gray-900 p-3 py-5">
							{chatHistory.map((c, i) => (
								<ChatMessage chat={c} key={i} />
							))}
							<div ref={ref}></div>
						</div>
						<div className="w-full bg-white dark:bg-gray-800 border-t dark:border-t-gray-600 flex items-center justify-between p-3">
							<div className="relative w-full mt-1 rounded-md shadow-sm">
								<input
									onKeyDown={(event) => {
										if (event.key === "Enter" && !lockChat) {
											sendMessage();
										}
									}}
									type="text"
									disabled={lockChat}
									value={lockChat ? "Thinking..." : chatValue}
									onChange={(e) => {
										setChatValue(e.target.value);
									}}
									className={classNames(
										lockChat ? "bg-gray-500 text-white" : "dark:bg-gray-700",
										"form-input block w-full rounded-md border-gray-300 dark:border-gray-600  dark:text-white pr-10 sm:text-sm"
									)}
									placeholder={"Send a message..."}
								/>
								<div className="absolute inset-y-0 right-0 flex items-center pr-3">
									<button disabled={lockChat} onClick={() => sendMessage()}>
										{lockChat ? (
											<LockClosedIcon
												className="h-5 w-5 text-gray-400  dark:hover:text-gray-300 animate-pulse"
												aria-hidden="true"
											/>
										) : (
											<PaperAirplaneIcon
												className="h-5 w-5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
												aria-hidden="true"
											/>
										)}
									</button>
								</div>
							</div>
						</div>
					</div>
				</div>
			</Transition>
			<Transition
				show={!open}
				appear={true}
				enter="transition ease-out duration-300"
				enterFrom="translate-y-96"
				enterTo="translate-y-0"
				leave="transition ease-in duration-300"
				leaveFrom="translate-y-0"
				leaveTo="translate-y-96"
			>
				<div className="absolute bottom-0 right-1">
					<div className="border flex justify-center align-center py-1 px-3 rounded-xl rounded-b-none bg-white dark:bg-gray-800 dark:border-gray-600 dark:text-white shadow">
						<button
							onClick={() => {
								setOpen(true);
							}}
						>
							<div className="flex gap-3  items-center">
								<Bars3CenterLeftIcon
									className="h-6 w-6 mt-1"
									style={{ color: nodeColors["chat"] }}
								/>
								Chat
							</div>
						</button>
					</div>
				</div>
			</Transition>
		</>
	);
}
