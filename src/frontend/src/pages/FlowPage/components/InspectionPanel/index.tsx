import { Panel } from "@xyflow/react";
import { motion, AnimatePresence } from "framer-motion";
import { memo, useState } from "react";
import type { AllNodeType } from "@/types/flow";
import { cn } from "@/utils/utils";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import InspectionPanelFields from "./components/InspectionPanelFields";
import InspectionPanelHeader from "./components/InspectionPanelHeader";
import InspectionPanelOutputs from "./components/InspectionPanelOutputs";
import InspectionPanelLogs from "./components/InspectionPanelLogs";

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
  const [activeTab, setActiveTab] = useState<"controls" | "outputs" | "logs">(
    "controls",
  );

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
            <Tabs
              value={activeTab}
              onValueChange={(value) =>
                setActiveTab(value as "controls" | "outputs" | "logs")
              }
              className="flex flex-col flex-1 overflow-hidden"
            >
              <TabsList className="w-full rounded-none !h-8">
                <TabsTrigger value="controls" className="flex-1 text-xs">
                  Controls
                </TabsTrigger>
                <TabsTrigger value="outputs" className="flex-1 text-xs">
                  Outputs
                </TabsTrigger>
                <TabsTrigger value="logs" className="flex-1 text-xs">
                  Logs
                </TabsTrigger>
              </TabsList>
              <TabsContent
                value="controls"
                className="overflow-y-auto flex-1 m-0"
              >
                <InspectionPanelFields data={selectedNode.data} />
              </TabsContent>
              <TabsContent
                value="outputs"
                className="overflow-y-auto flex-1 m-0"
              >
                <InspectionPanelOutputs data={selectedNode.data} />
              </TabsContent>
              <TabsContent value="logs" className="overflow-y-auto flex-1 m-0">
                <InspectionPanelLogs data={selectedNode.data} />
              </TabsContent>
            </Tabs>
          </motion.div>
        </Panel>
      )}
    </AnimatePresence>
  );
});

export default InspectionPanel;

// Made with Bob
