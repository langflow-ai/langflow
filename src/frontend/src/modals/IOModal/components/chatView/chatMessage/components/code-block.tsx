import { IconCheck, IconClipboard, IconDownload } from "@tabler/icons-react";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { tomorrow } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { programmingLanguages } from "../../../../../../constants/constants";
import { Props } from "../../../../../../types/components";

export function CodeBlock({ language, value }: Props): JSX.Element {
  const [isCopied, setIsCopied] = useState<Boolean>(false);

  const copyToClipboard = (): void => {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }

    navigator.clipboard.writeText(value).then(() => {
      setIsCopied(true);

      setTimeout(() => {
        setIsCopied(false);
      }, 2000);
    });
  };
  const downloadAsFile = (): void => {
    const fileExtension = programmingLanguages[language] || ".file";
    const suggestedFileName = `${"generated-code"}${fileExtension}`;
    const fileName = window.prompt("enter file name", suggestedFileName);

    if (!fileName) {
      // user pressed cancel on prompt
      return;
    }

    const blob = new Blob([value], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.download = fileName;
    link.href = url;
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };
  return (
    <div className="codeblock font-sans text-[16px]">
      <div className="code-block-modal">
        <span className="code-block-modal-span">{language}</span>

        <div className="flex items-center">
          <button className="code-block-modal-button" onClick={copyToClipboard}>
            {isCopied ? <IconCheck size={18} /> : <IconClipboard size={18} />}
            {isCopied ? "Copied!" : "Copy Code"}
          </button>
          <button className="code-block-modal-button" onClick={downloadAsFile}>
            <IconDownload size={18} />
          </button>
        </div>
      </div>

      <SyntaxHighlighter
        className="overflow-auto"
        language={language}
        style={tomorrow}
        customStyle={{ margin: 0 }}
      >
        {value}
      </SyntaxHighlighter>
    </div>
  );
}
CodeBlock.displayName = "CodeBlock";
