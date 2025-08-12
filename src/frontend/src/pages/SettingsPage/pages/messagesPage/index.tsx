import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import SessionView from "@/components/core/playgroundComponent/components/session-view";
import HeaderMessagesComponent from "./components/headerMessages";

export default function MessagesPage() {
	useGetMessagesQuery({ mode: "union" });

	return (
		<div className="flex h-full w-full flex-col justify-between gap-6">
			<HeaderMessagesComponent />
			<div className="flex h-full w-full flex-col justify-between">
				<SessionView />
			</div>
		</div>
	);
}
