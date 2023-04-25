import {
	ChatBubbleOvalLeftEllipsisIcon,
} from "@heroicons/react/24/outline";
import { useState } from "react";
import { ChatMessageType } from "../../../types/chat";
import { classNames } from "../../../utils";
import AiIcon from  "../../../assets/Gooey Ring-5s-271px.svg"
import { UserIcon } from "@heroicons/react/24/solid";
var Convert = require("ansi-to-html");
var convert = new Convert({ newline: true });

export default function ChatMessage({ chat }: { chat: ChatMessageType }) {
	const [hidden, setHidden] = useState(true);
	return (
		<div
			className={classNames(
				"w-full py-2 pl-2 flex",
				chat.isSend ? "bg-white" : "bg-gray-200"
			)}
		>
			<div
				className={classNames(
					"rounded-full w-9 h-9 flex items-center my-3 justify-center",chat.isSend?"bg-gray-200":"bg-gray-200"
				)}
			>
				{!chat.isSend && <img className="scale-150" src={AiIcon}/>}
				{chat.isSend && <UserIcon/>}
			</div>
			{!chat.isSend ? (
				<div className="w-full text-start flex items-center">
					<div
						className=" relative text-start inline-block text-gray-600 text-sm font-normal"
					>
						{hidden && chat.thought && chat.thought !== "" && (
							<div
								onClick={() => setHidden((prev) => !prev)}
								className="absolute -top-1 -left-2 cursor-pointer"
							>
								<ChatBubbleOvalLeftEllipsisIcon className="w-5 h-5 animate-bounce" />
							</div>
						)}
						{chat.thought && chat.thought !== "" && !hidden && (
							<div
								onClick={() => setHidden((prev) => !prev)}
								className=" text-start inline-block w-full pb-3 pt-3 px-5 cursor-pointer"
								dangerouslySetInnerHTML={{
									__html: convert.toHtml(chat.thought),
								}}
							></div>
						)}
						{chat.thought && chat.thought !== "" && !hidden && <br></br>}
						<div
							className="w-full rounded-b-md px-4 pb-3 pt-3 pr-8"
						>
							{chat.message}
						</div>
					</div>
				</div>
			) : (
				<div className="w-full flex items-center">
					<div className="text-start inline-block px-3 text-sm text-gray-600 dark:text-white dark:bg-gray-700">
						{chat.message}
					</div>
				</div>
			)}
		</div>
	);
}
