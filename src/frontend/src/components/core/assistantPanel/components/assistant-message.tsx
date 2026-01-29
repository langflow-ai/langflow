import { useContext } from "react";
import langflowAssistantIcon from "@/assets/langflow_assistant.svg";
import { AuthContext } from "@/contexts/authContext";
import { BASE_URL_API } from "@/customization/config-constants";
import { cn } from "@/utils/utils";
import type { AssistantMessage } from "../assistant-panel.types";

interface AssistantMessageItemProps {
  message: AssistantMessage;
}

export function AssistantMessageItem({ message }: AssistantMessageItemProps) {
  const { userData } = useContext(AuthContext);
  const isUser = message.role === "user";

  const profileImageUrl = `${BASE_URL_API}files/profile_pictures/${
    userData?.profile_image ?? "Space/046-rocket.svg"
  }`;

  return (
    <div className="mb-6">
      <div className="flex items-start gap-3">
        {isUser ? (
          <img
            src={profileImageUrl}
            alt="User"
            className="h-8 w-8 shrink-0 rounded-full"
          />
        ) : (
          <div className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-xl">
            <img
              src={langflowAssistantIcon}
              alt="Langflow Assistant"
              className="h-full w-full object-cover"
            />
          </div>
        )}
        <div className="flex flex-1 flex-col">
          <span
            className={cn(
              "text-[13px] font-semibold leading-4",
              isUser ? "text-foreground" : "text-accent-pink-foreground",
            )}
          >
            {isUser ? "User" : "Langflow Assistant"}
          </span>
          <p className="mt-1 text-sm font-normal leading-[22.75px] text-muted-foreground">
            {message.content}
          </p>
        </div>
      </div>
    </div>
  );
}
