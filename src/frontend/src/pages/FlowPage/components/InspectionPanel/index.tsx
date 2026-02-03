import { Panel } from "@xyflow/react";
import { motion, AnimatePresence } from "framer-motion";
import { memo } from "react";
import type { AllNodeType } from "@/types/flow";
import { cn } from "@/utils/utils";
import InspectionPanelFields from "./components/InspectionPanelFields";
import InspectionPanelHeader from "./components/InspectionPanelHeader";
import { Separator } from "@/components/ui/separator";

interface InspectionPanelProps {
  selectedNode: AllNodeType | null;
  isVisible: boolean;
  onClose?: () => void;
}

const InspectionPanel = memo(function InspectionPanel({
  selectedNode,
  isVisible,
  onClose,
}: InspectionPanelProps) {
  return (
    <AnimatePresence mode="wait">
      {isVisible && selectedNode && selectedNode.type === "genericNode" && (
        <Panel
          position="top-right"
          className={cn(
            "!top-[3rem] !-right-2 !bottom-10",
            "w-[320px]",
            "overflow-hidden pointer-events-none",
          )}
        >
          <motion.div
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0 }}
            transition={{ duration: 0, ease: "easeInOut" }}
            className={cn(
              "max-h-full w-full",
              "rounded-xl border bg-background shadow-lg",
              "overflow-y-auto flex flex-col pointer-events-auto",
            )}
          >
            <InspectionPanelHeader data={selectedNode.data} onClose={onClose} />
            <Separator className="my-0.5" />
            <InspectionPanelFields
              data={selectedNode.data}
              key={selectedNode.id}
            />
          </motion.div>
        </Panel>
      )}
    </AnimatePresence>
  );
});

export default InspectionPanel;
