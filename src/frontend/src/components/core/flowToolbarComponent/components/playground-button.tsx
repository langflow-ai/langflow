import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { SimpleSidebarTrigger } from "@/components/ui/simple-sidebar";

interface PlaygroundButtonProps {
  hasIO: boolean;
}

const PlaygroundButton = ({ hasIO }: PlaygroundButtonProps) => {
  const { t } = useTranslation();
  const label = t("toolbar.playground");

  const ButtonLabel = () => (
    <span className="font-normal text-mmd">{label}</span>
  );

  const DisabledButton = () => (
    <div
      className="relative inline-flex h-8 w-[7.2rem] items-center justify-start gap-1.5 rounded px-2 text-sm font-normal cursor-not-allowed text-muted-foreground"
      data-testid="playground-btn-flow"
    >
      <ForwardedIconComponent name="PanelRightOpen" className="h-4 w-4" />
      <ButtonLabel />
    </div>
  );

  return hasIO ? (
    <SimpleSidebarTrigger>
      <ButtonLabel />
    </SimpleSidebarTrigger>
  ) : (
    <ShadTooltip content={t("toolbar.addChatIOToPlayground")}>
      <div>
        <DisabledButton />
      </div>
    </ShadTooltip>
  );
};

export default PlaygroundButton;
