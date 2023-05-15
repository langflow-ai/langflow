import { LockClosedIcon, PaperAirplaneIcon } from "@heroicons/react/24/outline";
import { classNames } from "../../../utils";
import { useRef } from "react";

export default function ChatInput({
	lockChat,
	chatValue,
	sendMessage,
	setChatValue,
}: {
	lockChat: boolean;
	chatValue: string;
	sendMessage: Function;
	setChatValue: Function;
}) {
	const inputRef = useRef(null);
	return (
		<>
			<textarea
				onKeyDown={(event) => {
					if (event.key === "Enter" && !lockChat && !event.shiftKey) {
						sendMessage();
					}
				}}
				ref={inputRef}
				disabled={lockChat}
				style={{ resize: "none" }}
				value={lockChat ? "Thinking..." : chatValue}
				onChange={(e) => {
					setChatValue(e.target.value);
				}}
				className={classNames(
					lockChat ? "bg-gray-300 text-black dark:bg-gray-700 dark:text-gray-300" : "bg-gray-200 text-black dark:bg-gray-900 dark:text-gray-300",
					"form-input block w-full  custom-scroll h-10 rounded-md border-gray-300 dark:border-gray-600  pr-10 sm:text-sm"
				)}
				placeholder={"Send a message..."}
			/>
			<div className="absolute inset-y-0 right-0 flex items-center pr-3">
				<button disabled={lockChat} onClick={() => sendMessage()}>
					{lockChat ? (
						<LockClosedIcon
							className="h-5 w-5 text-gray-500  dark:hover:text-gray-300 animate-pulse"
							aria-hidden="true"
						/>
					) : (
						<PaperAirplaneIcon
							className="h-5 w-5 text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"
							aria-hidden="true"
						/>
					)}
				</button>
			</div>
		</>
	);
}
