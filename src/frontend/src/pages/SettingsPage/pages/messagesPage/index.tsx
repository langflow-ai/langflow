import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import SessionView from "@/modals/IOModal/components/session-view";
import HeaderMessagesComponent from "./components/headerMessages";

export default function MessagesPage() {
  useGetMessagesQuery({ mode: "union" });

  return (
    <div className="flex h-full w-full flex-col justify-between gap-4">
      <HeaderMessagesComponent />
      <div className="flex h-full flex-col gap-2 bg-background-surface border border-primary-border rounded-lg p-4">
        <SessionView />
      </div>
    </div>
  );
}
