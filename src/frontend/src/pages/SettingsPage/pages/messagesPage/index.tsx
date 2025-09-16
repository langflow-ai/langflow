import SessionView from "@/components/core/sessionViewComponent/session-view";
import HeaderMessagesComponent from "./components/headerMessages";

export default function MessagesPage() {
  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <HeaderMessagesComponent />
      <div className="flex h-full w-full flex-col justify-between">
        <SessionView />
      </div>
    </div>
  );
}
