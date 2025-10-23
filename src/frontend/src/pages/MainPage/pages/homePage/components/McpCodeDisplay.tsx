import { memo, type ReactNode } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";

interface MemoizedApiKeyButtonProps {
  apiKey: string;
  isGeneratingApiKey: boolean;
  generateApiKey: () => void;
}

export const MemoizedApiKeyButton = memo(
  ({
    apiKey,
    isGeneratingApiKey,
    generateApiKey,
  }: MemoizedApiKeyButtonProps) => (
    <Button
      unstyled
      className="flex items-center gap-2 font-sans text-muted-foreground hover:text-foreground"
      disabled={apiKey !== ""}
      loading={isGeneratingApiKey}
      onClick={generateApiKey}
    >
      <ForwardedIconComponent
        name={"key"}
        className="h-4 w-4"
        aria-hidden="true"
      />
      <span>{apiKey === "" ? "Generate API key" : "API key generated"}</span>
    </Button>
  ),
);
MemoizedApiKeyButton.displayName = "MemoizedApiKeyButton";

interface MemoizedCodeTagProps {
  children: ReactNode;
  isCopied: boolean;
  copyToClipboard: () => void;
  isAuthApiKey: boolean | null;
  apiKey: string;
  isGeneratingApiKey: boolean;
  generateApiKey: () => void;
}

export const MemoizedCodeTag = memo(
  ({
    children,
    isCopied,
    copyToClipboard,
    isAuthApiKey,
    apiKey,
    isGeneratingApiKey,
    generateApiKey,
  }: MemoizedCodeTagProps) => (
    <div className="relative bg-background text-[13px]">
      <div className="absolute right-4 top-4 flex items-center gap-6">
        {isAuthApiKey && (
          <MemoizedApiKeyButton
            apiKey={apiKey}
            isGeneratingApiKey={isGeneratingApiKey}
            generateApiKey={generateApiKey}
          />
        )}
        <Button
          unstyled
          size="icon"
          className={cn("h-4 w-4 text-muted-foreground hover:text-foreground")}
          onClick={copyToClipboard}
        >
          <ForwardedIconComponent
            name={isCopied ? "check" : "copy"}
            className="h-4 w-4"
            aria-hidden="true"
          />
        </Button>
      </div>
      <div className="overflow-x-auto p-4">
        <span>{children}</span>
      </div>
    </div>
  ),
);
MemoizedCodeTag.displayName = "MemoizedCodeTag";
