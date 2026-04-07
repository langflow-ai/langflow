import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { formatSeconds } from "@/components/core/playgroundComponent/chat-view/chat-messages/utils/format";
import { formatTokenCount } from "@/utils/format-token-count";

interface MessageMetadataProps {
  /** Duration in milliseconds */
  duration?: number;
  /** Token usage breakdown from LLM response */
  usage?: {
    total_tokens?: number | null;
    input_tokens?: number | null;
    output_tokens?: number | null;
  };
  /** Human-readable timestamp for the "Last run" tooltip line */
  timestamp?: string;
}

export default function MessageMetadata({
  duration,
  usage,
  timestamp,
}: MessageMetadataProps): JSX.Element | null {
  const hasDuration = typeof duration === "number" && duration > 0;
  const totalTokens = usage?.total_tokens;
  const hasTokens = typeof totalTokens === "number" && totalTokens > 0;

  if (!hasDuration && !hasTokens) return null;

  const tooltipContent = (
    <div className="flex flex-col gap-1">
      {timestamp && (
        <div className="flex items-center text-xxs text-secondary-foreground">
          <div>Last run:</div>
          <div className="ml-1">{timestamp}</div>
        </div>
      )}
      {hasDuration && (
        <div className="flex items-center text-xxs text-secondary-foreground">
          <div>Duration:</div>
          <div className="ml-auto">{formatSeconds(duration)}</div>
        </div>
      )}
      {usage?.input_tokens != null && (
        <div className="flex items-center text-xxs text-secondary-foreground">
          <div>Input:</div>
          <div className="ml-auto flex items-center gap-1 font-mono text-xs">
            <ForwardedIconComponent name="Coins" className="h-3 w-3" />
            {formatTokenCount(usage.input_tokens)}
          </div>
        </div>
      )}
      {usage?.output_tokens != null && (
        <div className="flex items-center text-xxs text-secondary-foreground">
          <div>Output:</div>
          <div className="ml-auto flex items-center gap-1 font-mono text-xs">
            <ForwardedIconComponent name="Coins" className="h-3 w-3" />
            {formatTokenCount(usage.output_tokens)}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <ShadTooltip
      content={tooltipContent}
      styleClasses="border rounded-xl p-2 bg-background"
      side="bottom"
    >
      <span
        data-testid="chat-message-token-usage"
        className="ml-auto flex cursor-help items-center gap-1 font-mono text-xs font-normal text-accent-emerald-foreground"
      >
        {hasTokens && (
          <span className="flex items-center gap-1">
            <ForwardedIconComponent
              name="Coins"
              className="h-3 w-3 text-muted-foreground"
            />
            <span>{formatTokenCount(totalTokens)}</span>
            {hasDuration && <span className="text-muted-foreground">|</span>}
          </span>
        )}
        {hasDuration && <span>{formatSeconds(duration)}</span>}
      </span>
    </ShadTooltip>
  );
}
