import { useEffect, useRef } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ChatMessageBubble from "./chat-message-bubble";
import type { ChatMessage } from "./types";

interface ChatMessagesProps {
  messages: ChatMessage[];
}

function EmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-border">
        <ForwardedIconComponent name="Bot" className="h-6 w-6" />
      </div>
      <span className="text-sm">Agent Chat</span>
    </div>
  );
}

export default function ChatMessages({ messages }: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length]);

  if (messages.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
      {messages.map((message) => (
        <ChatMessageBubble key={message.id} message={message} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
