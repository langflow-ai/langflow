import { cn } from "@/utils/utils";
import type { ChatViewWrapperProps } from "../types/chat-view-wrapper";
import ChatView from "./chatView/components/chat-view";

export const ChatViewWrapper = ({
	selectedViewField,
	visibleSession,
	messagesFetched,
	sessionId,
	sendMessage,
	playgroundPage,
}: ChatViewWrapperProps) => {
	return (
		<div
			className={cn(
				"flex h-full flex-col justify-between px-4 pb-4 pt-2",
				selectedViewField ? "hidden" : "",
			)}
		>
			<ChatView
				focusChat={sessionId}
				sendMessage={sendMessage}
				visibleSession={visibleSession}
				playgroundPage={playgroundPage}
			/>
		</div>
	);
};
