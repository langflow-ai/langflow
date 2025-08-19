import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import {
  BUG_REPORT_URL,
  DATASTAX_DOCS_URL,
  DESKTOP_URL,
  DOCS_URL,
} from "@/constants/constants";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import useFlowStore from "@/stores/flowStore";
import DropdownControlButton from "./DropdownControlButton";

const HelpDropdown = () => {
  const navigate = useNavigate();
  const [isHelpMenuOpen, setIsHelpMenuOpen] = useState(false);
  const helperLineEnabled = useFlowStore((state) => state.helperLineEnabled);
  const setHelperLineEnabled = useFlowStore(
    (state) => state.setHelperLineEnabled,
  );

  const onToggleHelperLines = useCallback(() => {
    setHelperLineEnabled(!helperLineEnabled);
  }, [helperLineEnabled]);

  return (
    <DropdownMenu open={isHelpMenuOpen} onOpenChange={setIsHelpMenuOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="group flex items-center justify-center px-2 rounded-none"
          title="Help"
        >
          <IconComponent
            name="Circle-Help"
            aria-hidden="true"
            className="text-muted-foreground group-hover:text-primary !h-5 !w-5"
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side="top"
        align="end"
        className="flex flex-col w-full"
      >
        <DropdownControlButton
          iconName="book-open"
          testId="canvas_controls_dropdown_docs"
          label="Docs"
          externalLink
          onClick={() => {
            window.open(
              ENABLE_DATASTAX_LANGFLOW ? DATASTAX_DOCS_URL : DOCS_URL,
              "_blank",
            );
          }}
        />
        <DropdownControlButton
          iconName="keyboard"
          testId="canvas_controls_dropdown_shortcuts"
          label="Shortcuts"
          onClick={() => {
            navigate("/settings/shortcuts");
          }}
        />
        <DropdownControlButton
          iconName="bug"
          testId="canvas_controls_dropdown_report_a_bug"
          externalLink
          label="Report a bug"
          onClick={() => {
            window.open(BUG_REPORT_URL, "_blank");
          }}
        />
        <Separator />
        <DropdownControlButton
          iconName="download"
          testId="canvas_controls_dropdown_get_langflow_desktop"
          label="Get Langflow Desktop"
          externalLink
          onClick={() => {
            window.open(DESKTOP_URL, "_blank");
          }}
        />
        <DropdownControlButton
          iconName={!helperLineEnabled ? "UnfoldHorizontal" : "FoldHorizontal"}
          testId="canvas_controls_dropdown_enable_smart_guides"
          onClick={onToggleHelperLines}
          toggleValue={helperLineEnabled}
          label="Enable smart guides"
          hasToogle={true}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default HelpDropdown;
