import { useCallback, useEffect, useRef } from "react";
import { useUtilityStore } from "@/stores/utilityStore";
import type { ChatMessageType } from "@/types/chat";

interface ChatScrollAnchorProps {
	trackVisibility: ChatMessageType;
	canScroll: boolean;
}

export function ChatScrollAnchor({
	trackVisibility,
	canScroll,
}: ChatScrollAnchorProps) {
	const scrollRef = useRef<HTMLDivElement>(null);

	const playgroundScrollBehaves = useUtilityStore(
		(state) => state.playgroundScrollBehaves,
	);
	const setPlaygroundScrollBehaves = useUtilityStore(
		(state) => state.setPlaygroundScrollBehaves,
	);

	const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
		if (!scrollRef.current) return;

		// Find the closest scrollable container with class "chat-message-div"
		const messagesContainer = scrollRef.current.closest(".chat-message-div");
		if (messagesContainer) {
			// Scroll the messages container to bottom
			messagesContainer.scrollTo({
				top: messagesContainer.scrollHeight,
				behavior: behavior,
			});
		} else {
			// Fallback to scrollIntoView if container not found
			scrollRef.current.scrollIntoView({
				behavior: behavior,
				block: "end",
			});
		}
	}, []);

	useEffect(() => {
		if (canScroll) {
			if (!scrollRef.current) return;

			if (trackVisibility.category === "error") {
				scrollToBottom(playgroundScrollBehaves);
				setTimeout(() => {
					scrollToBottom("smooth");
				}, 400);
			} else {
				scrollToBottom(playgroundScrollBehaves);
				if (playgroundScrollBehaves === "smooth") {
					setPlaygroundScrollBehaves("instant");
					setTimeout(() => {
						scrollToBottom("instant");
					}, 200);
				}
			}
		}
	}, [
		trackVisibility,
		canScroll,
		scrollToBottom,
		playgroundScrollBehaves,
		setPlaygroundScrollBehaves,
	]);

	return <div ref={scrollRef} className="h-px w-full" />;
}
