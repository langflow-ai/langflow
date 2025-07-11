import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import { type ButtonHTMLAttributes, useState } from "react";

export function EditMessageButton({
  onEdit,
  onCopy,
  onEvaluate,
  isBotMessage,
  evaluation,
  isAudioMessage,
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  onEdit: () => void;
  onCopy: () => void;
  onDelete: () => void;
  onEvaluate?: (value: boolean | null) => void;
  isBotMessage?: boolean;
  evaluation?: boolean | null;
  isAudioMessage?: boolean;
}) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = () => {
    onCopy();
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleEvaluate = (value: boolean) => {
    onEvaluate?.(evaluation === value ? null : value);
  };

  return (
    <div className="flex items-center rounded-md border border-border bg-background">
      {!isAudioMessage && (
        <ShadTooltip styleClasses="z-50" content="Edit message" side="top">
          <div className="p-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={onEdit}
              className="h-8 w-8"
            >
              <IconComponent name="Pen" className="h-4 w-4" />
            </Button>
          </div>
        </ShadTooltip>
      )}

      <ShadTooltip
        styleClasses="z-50"
        content={isCopied ? "Copied!" : "Copy message"}
        side="top"
      >
        <div className="p-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleCopy}
            className="h-8 w-8"
          >
            <IconComponent
              name={isCopied ? "Check" : "Copy"}
              className="h-4 w-4"
            />
          </Button>
        </div>
      </ShadTooltip>

      {isBotMessage && (
        <div className="flex">
          <ShadTooltip styleClasses="z-50" content="Helpful" side="top">
            <div className="p-1">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleEvaluate(true)}
                className="h-8 w-8"
                data-testid="helpful-button"
              >
                <IconComponent
                  name={evaluation === true ? "ThumbUpIconCustom" : "ThumbsUp"}
                  className={cn("h-4 w-4")}
                />
              </Button>
            </div>
          </ShadTooltip>

          <ShadTooltip styleClasses="z-50" content="Not helpful" side="top">
            <div className="p-1">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleEvaluate(false)}
                className="h-8 w-8"
                data-testid="not-helpful-button"
              >
                <IconComponent
                  name={
                    evaluation === false ? "ThumbDownIconCustom" : "ThumbsDown"
                  }
                  className={cn("h-4 w-4")}
                />
              </Button>
            </div>
          </ShadTooltip>
        </div>
      )}
    </div>
  );
}
