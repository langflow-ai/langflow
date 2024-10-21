import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useDarkStore } from "../../stores/darkStore";
import { Button } from "../ui/button";
import IconComponent from "../genericIconComponent";

type SimplifiedCodeTabProps = {
  code: string;
  language: string;
  description?: string;
};

export default function SimplifiedCodeTabComponent({
  code,
  language,
  description,
}: SimplifiedCodeTabProps) {
  const [isCopied, setIsCopied] = useState<boolean>(false);
  const dark = useDarkStore((state) => state.dark);

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
    <div className="flex h-full flex-col overflow-hidden rounded-md border bg-zinc-700 text-center inset-0 m-0 dark">
      <div className="api-modal-tablist-div flex justify-between items-center px-2 py-1">
        <div className="text-sm text-muted-foreground">{language}</div>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground"
          onClick={copyToClipboard}
        >
          {isCopied ? (
            <IconComponent name="Check" className="h-4 w-4" />
          ) : (
            <IconComponent name="Copy" className="h-4 w-4" />
          )}
        </Button>
      </div>

      <div className="flex h-full w-full flex-col">
        {description && (
          <div
            className="mb-2 w-full text-left text-sm px-2"
            dangerouslySetInnerHTML={{ __html: description }}
          ></div>
        )}
        <SyntaxHighlighter
          language={language}
          style={oneDark}
          className="mt-0 h-full overflow-auto rounded-sm text-left custom-scroll"
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}
