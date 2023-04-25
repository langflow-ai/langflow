import { Dialog, Transition } from "@headlessui/react";
import {
	XMarkIcon,
	ClipboardDocumentListIcon,
	LockClosedIcon,
	PaperAirplaneIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useEffect, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { NodeType } from "../../types/flow";
import { TabsContext } from "../../contexts/tabsContext";
import { alertContext } from "../../contexts/alertContext";
import { classNames, snakeToNormalCase } from "../../utils";
import { sendAll } from "../../controllers/API";
import { typesContext } from "../../contexts/typesContext";
import ChatMessage from "../../components/chatComponent/chatMessage";
const _ = require("lodash");

export default function ChatModal({ flow }) {
	const { updateFlow, lockChat, setLockChat, flows, tabIndex } =
		useContext(TabsContext);
	const [saveChat, setSaveChat] = useState(false);
	const [chatValue, setChatValue] = useState("");
	const [chatHistory, setChatHistory] = useState(flow.chat);
	const { reactFlowInstance } = useContext(typesContext);
	const { setErrorData, setNoticeData } = useContext(alertContext);
	const addChatHistory = (
		message: string,
		isSend: boolean,
		thought?: string
	) => {
		let tabsChange = false;
		setChatHistory((old) => {
			let newChat = _.cloneDeep(old);
			if (JSON.stringify(flow.chat) !== JSON.stringify(old)) {
				tabsChange = true;
				return old;
			}
			if (thought) {
				newChat.push({ message, isSend, thought });
			} else {
				newChat.push({ message, isSend });
			}
			return newChat;
		});
		if (tabsChange) {
			if (thought) {
				updateFlow({
					..._.cloneDeep(flow),
					chat: [...flow.chat, { isSend, message, thought }],
				});
			} else {
				updateFlow({
					..._.cloneDeep(flow),
					chat: [...flow.chat, { isSend, message }],
				});
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
						(!template[t].value || template[t].value === "") &&
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
										: snakeToNormalCase(template[t].name)
								}.`,
						  ]
						: []
				),
			[] as string[]
		);
	}

	function validateNodes() {
		console.log(reactFlowInstance)
		return reactFlowInstance
			.getNodes()
			.flatMap((n: NodeType) => validateNode(n));
	}

	const ref = useRef(null);

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
				})
					.then((r) => {
						addChatHistory(r.data.result, false, r.data.thought);
						setLockChat(false);
					})
					.catch((error) => {
						setErrorData({
							title: error.message ?? "Unknown Error",
							list: [error.response.data.detail],
						});
						setLockChat(false);
						let lastMessage;
						setChatHistory((chatHistory) => {
							let newChat = chatHistory;

							lastMessage = newChat.pop().message;
							return newChat;
						});
						setChatValue(lastMessage);
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
		updateFlow({ ..._.cloneDeep(flow), chat: [] });
	}

	const [open, setOpen] = useState(true);
	const { closePopUp } = useContext(PopUpContext);
	function setModalOpen(x: boolean) {
		setOpen(x);
		if (x === false) {
			setTimeout(() => {
				closePopUp();
			}, 300);
		}
	}
	return (
		<Transition.Root show={open} appear={true} as={Fragment}>
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
					<div className="fixed inset-0 bg-gray-500 dark:bg-gray-600 dark:bg-opacity-75 bg-opacity-75 transition-opacity" />
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
							<Dialog.Panel className="relative flex flex-col justify-between transform h-[600px] overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-left shadow-xl transition-all sm:my-8 w-[700px]">
								<div className="w-full h-full bg-white dark:bg-gray-800 border-t dark:border-t-gray-600 flex-col flex items-center justify-between p-3">
									{chatHistory.map((c, i) => (
										<ChatMessage chat={c} key={i} />
									))}
									<div ref={ref}></div>
								</div>
								<div className="w-full bg-white dark:bg-gray-800 border-t dark:border-t-gray-600 flex-col flex items-center justify-between p-3">
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
												lockChat
													? "bg-gray-500 text-white"
													: "dark:bg-gray-700",
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
							</Dialog.Panel>
						</Transition.Child>
					</div>
				</div>
			</Dialog>
		</Transition.Root>
	);
}
