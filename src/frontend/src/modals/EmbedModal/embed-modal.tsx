import { useDarkStore } from "@/stores/darkStore";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
  oneDark,
  oneLight,
} from "react-syntax-highlighter/dist/cjs/styles/prism";
import IconComponent from "../../components/common/genericIconComponent";
import { Button } from "../../components/ui/button";
import getWidgetCode from "../apiModal/utils/get-widget-code";
import BaseModal from "../baseModal";

interface EmbedModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowId: string;
  flowName: string;
  isAuth: boolean;
  tweaksBuildedObject: {};
  activeTweaks: boolean;
}

export default function EmbedModal({
  open,
  setOpen,
  flowId,
  flowName,
  isAuth,
  tweaksBuildedObject,
  activeTweaks,
}: EmbedModalProps) {
  const isDark = useDarkStore((state) => state.dark);
  const [isCopied, setIsCopied] = useState<boolean>(false);
  const widgetProps = {
    flowId: flowId,
    flowName: flowName,
    isAuth: isAuth,
    tweaksBuildedObject: tweaksBuildedObject,
    activeTweaks: activeTweaks,
  };
  const embedCode = getWidgetCode({ ...widgetProps, copy: false });
  const copyCode = getWidgetCode({ ...widgetProps, copy: true });
  const copyToClipboard = () => {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }

    navigator.clipboard.writeText(copyCode).then(() => {
      setIsCopied(true);

      setTimeout(() => {
        setIsCopied(false);
      }, 2000);
    });
  };

  return (
    <BaseModal open={open} setOpen={setOpen} size="retangular">
      <BaseModal.Header>
        <div className="flex items-center gap-2 text-base font-semibold">
          <IconComponent name="Columns2" className="icon-size" />
          Embed into site
        </div>
      </BaseModal.Header>
      <BaseModal.Content className="">
        <div className="relative flex h-full w-full">
          <Button
            variant="ghost"
            size="icon"
            onClick={copyToClipboard}
            data-testid="btn-copy-code"
            className="!hover:bg-foreground group absolute top-2 right-2"
          >
            {isCopied ? (
              <IconComponent
                name="Check"
                className="text-muted-foreground h-5 w-5"
              />
            ) : (
              <IconComponent
                name="Copy"
                className="text-muted-foreground h-5! w-5!"
              />
            )}
          </Button>
          <SyntaxHighlighter
            showLineNumbers={true}
            wrapLongLines={true}
            language="html"
            style={isDark ? oneDark : oneLight}
            className="border-border custom-scroll! mt-0! h-full w-full overflow-scroll rounded-b-md! border text-left"
          >
            {embedCode}
          </SyntaxHighlighter>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
