import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import DropdownControlButton from "./DropdownControlButton";

export type HelpDropdownViewProps = {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  helperLineEnabled: boolean;
  onToggleHelperLines: () => void;
  navigateTo: (path: string) => void;
  openLink: (url: string) => void;
  urls: {
    docs: string;
    bugReport: string;
    desktop: string;
  };
};

export const HelpDropdownView = ({
  isOpen,
  onOpenChange,
  helperLineEnabled,
  onToggleHelperLines,
  navigateTo,
  openLink,
  urls,
}: HelpDropdownViewProps) => {
  const { t } = useTranslation();
  return (
    <DropdownMenu open={isOpen} onOpenChange={onOpenChange}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="group flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
          title={t("help.title")}
          data-testid="canvas_controls_dropdown_help"
        >
          <IconComponent
            name="Circle-Help"
            aria-hidden="true"
            className="text-muted-foreground group-hover:text-foreground !h-5 !w-5"
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side="top"
        align="center"
        className="flex flex-col w-full"
      >
        <DropdownControlButton
          iconName="book-open"
          testId="canvas_controls_dropdown_docs"
          label={t("help.docs")}
          externalLink
          onClick={() => openLink(urls.docs)}
        />
        <DropdownControlButton
          iconName="keyboard"
          testId="canvas_controls_dropdown_shortcuts"
          label={t("help.shortcuts")}
          onClick={() => navigateTo("/settings/shortcuts")}
        />
        <DropdownControlButton
          iconName="bug"
          testId="canvas_controls_dropdown_report_a_bug"
          externalLink
          label={t("help.reportBug")}
          onClick={() => openLink(urls.bugReport)}
        />
        <Separator />
        <DropdownControlButton
          iconName="download"
          testId="canvas_controls_dropdown_get_langflow_desktop"
          label={t("help.getLangflowDesktop")}
          externalLink
          onClick={() => openLink(urls.desktop)}
        />
        <DropdownControlButton
          iconName={!helperLineEnabled ? "UnfoldHorizontal" : "FoldHorizontal"}
          testId="canvas_controls_dropdown_enable_smart_guides"
          onClick={onToggleHelperLines}
          toggleValue={helperLineEnabled}
          label={t("help.enableSmartGuides")}
          hasToogle={true}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default HelpDropdownView;
