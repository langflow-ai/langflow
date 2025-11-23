import { type ButtonHTMLAttributes, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";

export function EditMessageButton({
  onEdit,
  onCopy,
  isAudioMessage,
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  onEdit: () => void;
  onCopy: () => void;
  isAudioMessage?: boolean;
}) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = () => {
    onCopy();
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
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
    </div>
  );
}
