import { Panel } from "@xyflow/react";
import { AnimatePresence, motion } from "framer-motion";
import { memo, useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Separator } from "@/components/ui/separator";
import {
  INSPECTION_PANEL_EMPTY_MIN_HEIGHT,
  INSPECTION_PANEL_INNER_WIDTH,
  INSPECTION_PANEL_OUTER_WIDTH,
} from "@/constants/constants";
import type { AllNodeType } from "@/types/flow";
import { cn } from "@/utils/utils";
import InspectionPanelFields from "./components/InspectionPanelFields";
import InspectionPanelHeader from "./components/InspectionPanelHeader";

interface InspectionPanelProps {
  selectedNode: AllNodeType | null;
  isVisible: boolean;
}

const InspectionPanel = memo(function InspectionPanel({
  selectedNode,
  isVisible,
}: InspectionPanelProps) {
  const [isEditingFields, setIsEditingFields] = useState(false);

  // Reset edit mode when panel closes or node changes
  useEffect(() => {
    setIsEditingFields(false);
  }, [selectedNode?.id, isVisible]);

  const hasValidSelection = selectedNode && selectedNode.type === "genericNode";

  return (
    <AnimatePresence mode="wait">
      {isVisible && (
        <Panel
          position="top-right"
          style={{ width: INSPECTION_PANEL_OUTER_WIDTH }}
          className={cn(
            "!top-[3rem] !-right-2 !bottom-10 relative",
            "pointer-events-none",
          )}
        >
          <motion.div
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0 }}
            transition={{ duration: 0, ease: "easeInOut" }}
            style={{ width: INSPECTION_PANEL_INNER_WIDTH }}
            className={cn(
              "max-h-full ml-auto",
              "rounded-xl border bg-background shadow-lg",
              "overflow-y-auto overflow-x-visible flex flex-col pointer-events-auto",
            )}
          >
            {hasValidSelection ? (
              <>
                <InspectionPanelHeader
                  data={selectedNode.data}
                  isEditingFields={isEditingFields}
                  setIsEditingFields={setIsEditingFields}
                />
                <Separator className="my-0.5" />
                <InspectionPanelFields
                  data={selectedNode.data}
                  key={selectedNode.id}
                  isEditingFields={isEditingFields}
                />
              </>
            ) : (
              <div
                style={{ minHeight: INSPECTION_PANEL_EMPTY_MIN_HEIGHT }}
                className="flex flex-col items-center justify-center p-8 text-center h-full"
              >
                <ForwardedIconComponent
                  name="MousePointerClick"
                  className="h-12 w-12 text-muted-foreground/50 mb-4"
                />
                <p className="text-sm text-muted-foreground">
                  Select a component to inspect its properties
                </p>
              </div>
            )}
          </motion.div>
        </Panel>
      )}
    </AnimatePresence>
  );
});

export default InspectionPanel;
