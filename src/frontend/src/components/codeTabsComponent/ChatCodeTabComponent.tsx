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
    <div className="flex flex-col w-full overflow-hidden rounded-md border border-gray-700 bg-[#1e1e1e] text-left">
      <div className="flex justify-between w-full items-center px-4 py-2 bg-[#2d2d2d] border-b border-gray-700">
        <span className="text-sm text-gray-400">{language}</span>
        <Button
          variant="ghost"
          size="icon"
          className="text-gray-400 hover:bg-[#3a3a3a]"
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
        className="mt-0 h-full w-full overflow-auto rounded-sm text-left custom-scroll"
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
