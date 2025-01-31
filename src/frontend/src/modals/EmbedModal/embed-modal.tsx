import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import BaseModal from "../baseModal";
import IconComponent from "../../components/common/genericIconComponent";
import { Button } from "../../components/ui/button";

interface EmbedModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  embedCode: string;
}

export default function EmbedModal({ open, setOpen, embedCode }: EmbedModalProps) {
  const [isCopied, setIsCopied] = useState<boolean>(false);

  const copyToClipboard = () => {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }

    navigator.clipboard.writeText(embedCode).then(() => {
      setIsCopied(true);

      setTimeout(() => {
        setIsCopied(false);
      }, 2000);
    });
  };

  return (
    <BaseModal open={open} setOpen={setOpen} size="medium">
      <BaseModal.Header description="Copy and paste this code into your website to embed the chat interface.">
        Embed into site
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="mt-2 flex h-full w-full flex-col">
          <div className="flex w-full items-center justify-end gap-4 rounded-t-md border border-border bg-muted px-4 py-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={copyToClipboard}
              data-testid="btn-copy-code"
            >
              {isCopied ? (
                <IconComponent
                  name="Check"
                  className="h-4 w-4 text-muted-foreground"
                />
              ) : (
                <IconComponent
                  name="Copy"
                  className="h-4 w-4 text-muted-foreground"
                />
              )}
            </Button>
          </div>
          <SyntaxHighlighter
            language="html"
            style={oneDark}
            className="!mt-0 h-full w-full overflow-scroll !rounded-b-md !rounded-t-none border border-border text-left !custom-scroll"
          >
            {embedCode}
          </SyntaxHighlighter>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
