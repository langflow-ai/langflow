import { Panel } from "@xyflow/react";
import { motion, AnimatePresence } from "framer-motion";
import { memo, useState, useEffect } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { AllNodeType } from "@/types/flow";
import { cn } from "@/utils/utils";
import InspectionPanelFields from "./components/InspectionPanelFields";
import InspectionPanelHeader from "./components/InspectionPanelHeader";
import { Separator } from "@/components/ui/separator";

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

  const hasValidSelection =
    selectedNode && selectedNode.type === "genericNode";

  return (
    <AnimatePresence mode="wait">
      {isVisible && (
        <Panel
          position="top-right"
          className={cn(
            "!top-[3rem] !-right-2 !bottom-10 relative",
            "w-[340px]",
            "pointer-events-none",
          )}
        >
          <motion.div
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0 }}
            transition={{ duration: 0, ease: "easeInOut" }}
            className={cn(
              "max-h-full w-[320px] ml-auto",
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
              <div className="flex flex-col items-center justify-center p-8 text-center h-full min-h-[200px]">
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
