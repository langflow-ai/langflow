import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useDarkStore } from "../../stores/darkStore";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";

type SimplifiedCodeTabProps = {
  code: string;
  language: string;
};

export default function SimplifiedCodeTabComponent({
  code,
  language,
}: SimplifiedCodeTabProps) {
  const [isCopied, setIsCopied] = useState<boolean>(false);

  const copyToClipboard = () => {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }

    navigator.clipboard.writeText(code).then(() => {
      setIsCopied(true);

      setTimeout(() => {
        setIsCopied(false);
      }, 2000);
    });
  };

  return (
    <div className="flex w-full flex-col overflow-hidden rounded-md text-left dark">
      <div className="flex w-full items-center justify-between rounded-t-md border border-border bg-accent px-4 py-2">
        <span className="dar text-sm font-semibold text-white">{language}</span>
        <Button
          variant="ghost"
          size="icon"
          className="bg-card text-muted-foreground"
          data-testid="copy-code-button"
          onClick={copyToClipboard}
        >
          {isCopied ? (
            <IconComponent name="Check" className="h-4 w-4" />
          ) : (
            <IconComponent name="Copy" className="h-4 w-4" />
          )}
        </Button>
      </div>
      <SyntaxHighlighter
        language={language.toLowerCase()}
        style={oneDark}
        className="!mt-0 h-full w-full overflow-scroll !rounded-b-md !rounded-t-none border border-border text-left !custom-scroll"
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
