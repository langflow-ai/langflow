
import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import HeaderMessagesComponent from "./components/headerMessages";
import SessionView from "@/modals/IOModal/components/SessionView";

export default function MessagesPage() {

  useGetMessagesQuery({mode:"union"})

  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <HeaderMessagesComponent />
      <div className="flex h-full w-full flex-col justify-between">
        <SessionView />
      </div>
    </div>
  );
}
