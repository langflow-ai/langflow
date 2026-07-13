import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import a11yLight from "react-syntax-highlighter/dist/cjs/styles/prism/a11y-one-light";
import { useDarkStore } from "@/stores/darkStore";
import IconComponent from "../../common/genericIconComponent";
import { Button } from "../../ui/button";

type SimplifiedCodeTabProps = {
  code: string;
  language: string;
  maxHeight?: string;
  // Override the light-mode syntax theme. Defaults to a11yLight (WCAG-compliant
  // contrast on bg-canvas). Pass a different prism style object if your call
  // site uses a background where a11yLight's palette causes contrast issues.
  lightStyle?: { [key: string]: React.CSSProperties };
};

export default function SimplifiedCodeTabComponent({
  code,
  language,
  maxHeight,
  lightStyle = a11yLight,
}: SimplifiedCodeTabProps) {
  const { t } = useTranslation();
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
    <div
      className="mt-2 flex w-full flex-col overflow-hidden rounded-md text-left"
      data-testid="chat-code-tab"
    >
      <div className="flex w-full items-center justify-between rounded-t-md border border-b-0 border-border bg-canvas px-4 py-2">
        <span className="text-sm font-semibold text-foreground">
          {language}
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:bg-card"
          data-testid="copy-code-button"
          onClick={copyToClipboard}
          aria-label={isCopied ? t("chat.copiedCode") : t("chat.copyCode")}
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
        style={dark ? oneDark : lightStyle}
        className="!mt-0 h-full w-full overflow-auto !bg-canvas [&_code]:!bg-canvas !rounded-b-md !rounded-t-none border border-border text-left custom-scroll"
        customStyle={maxHeight ? { maxHeight } : undefined}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
