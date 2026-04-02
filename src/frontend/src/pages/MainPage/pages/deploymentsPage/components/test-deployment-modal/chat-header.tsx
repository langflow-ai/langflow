interface ChatHeaderProps {
  deploymentName: string;
}

export default function ChatHeader({ deploymentName }: ChatHeaderProps) {
  return (
    <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
      <span className="font-semibold text-sm">{deploymentName}</span>
      <div className="h-2 w-2 rounded-full bg-status-green flex-shrink-0" />
    </div>
  );
}
