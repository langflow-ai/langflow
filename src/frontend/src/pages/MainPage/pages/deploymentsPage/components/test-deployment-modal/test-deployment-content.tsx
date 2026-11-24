import ChatHeader from "./chat-header";
import ChatInput from "./chat-input";
import ChatMessages from "./chat-messages";
import { useDeploymentChat } from "./use-deployment-chat";

interface TestDeploymentContentProps {
  deployment: { id: string; name: string } | null;
  providerId: string;
}

export default function TestDeploymentContent({
  deployment,
  providerId,
}: TestDeploymentContentProps) {
  const { messages, isWaitingForResponse, sendMessage } = useDeploymentChat({
    providerId,
    deploymentId: deployment?.id ?? "",
  });

  return (
    <>
      <ChatHeader deploymentName={deployment?.name ?? ""} />
      <ChatMessages messages={messages} />
      <ChatInput onSend={sendMessage} disabled={isWaitingForResponse} />
    </>
  );
}
