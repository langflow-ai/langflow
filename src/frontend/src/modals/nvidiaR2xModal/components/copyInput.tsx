import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import { useState } from "react";

export function CopyInput({
  value,
  label,
  copyButton,
}: {
  value: string;
  label?: string;
  copyButton?: boolean;
}) {
  const [isCopied, setIsCopied] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard
      .writeText(value)
      .then(() => {
        setIsCopied(true);
        setTimeout(() => {
          setIsCopied(false);
        }, 1000);
      })
      .catch((err) => console.error("Failed to copy text: ", err));
  };
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-sm font-medium">{label}</label>}

      <div className="relative">
        <Input
          id="sidebar-name-input"
          disabled
          onChange={() => {}}
          readOnly
          className={cn("select-text", copyButton ? "pr-14" : "pr-8")}
          maxLength={46}
          placeholder=""
          data-testid="input_update_name"
        />
        <div className="absolute top-1/2 flex w-full -translate-y-1/2 cursor-text">
          <div
            className={cn(
              "mr-10 flex-1 cursor-text select-text text-nowrap pl-3 text-sm text-muted-foreground truncate-accent",
              copyButton && "mr-14",
            )}
          >
            <span>{value}</span>
          </div>
        </div>
        <Button
          unstyled
          onClick={copyToClipboard}
          className={cn(
            "absolute right-3 top-1/2 z-20 -translate-y-1/2",
            copyButton &&
              "right-0 h-full w-[3.2rem] rounded-r-lg border-l bg-primary",
          )}
        >
          {copyButton ? (
            <span className="flex w-full items-center justify-center text-mmd font-semibold text-secondary">
              {isCopied ? (
                <ForwardedIconComponent name="Check" className="h-4 w-4" />
              ) : (
                "Copy"
              )}
            </span>
          ) : (
            <ForwardedIconComponent
              name={isCopied ? "Check" : "Copy"}
              className="h-4 w-4 text-primary"
            />
          )}
        </Button>
      </div>
    </div>
  );
}
