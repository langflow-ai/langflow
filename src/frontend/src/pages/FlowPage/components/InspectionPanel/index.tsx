import { Panel } from "@xyflow/react";
import { motion, AnimatePresence } from "framer-motion";
import { memo } from "react";
import type { AllNodeType } from "@/types/flow";
import { cn } from "@/utils/utils";
import InspectionPanelFields from "./components/InspectionPanelFields";
import InspectionPanelHeader from "./components/InspectionPanelHeader";

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
            "overflow-hidden",
          )}
        >
          <motion.div
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className={cn(
              "h-full w-full",
              "rounded-xl border bg-background shadow-lg",
              "overflow-hidden flex flex-col",
            )}
          >
            <InspectionPanelHeader data={selectedNode.data} onClose={onClose} />
            <div className="overflow-y-auto flex-1">
              <InspectionPanelFields data={selectedNode.data} />
            </div>
          </motion.div>
        </Panel>
      )}
    </AnimatePresence>
  );
});

export default InspectionPanel;

// Made with Bob
