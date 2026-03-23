import { useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import ScheduleModal from "@/modals/scheduleModal";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

const ScheduleButton = () => {
  const [openScheduleModal, setOpenScheduleModal] = useState(false);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const flowId = currentFlow?.id;

  if (!flowId) return null;

  return (
    <>
      <Button
        variant="ghost"
        size="md"
        className="!px-2.5 font-normal"
        onClick={() => setOpenScheduleModal(true)}
        data-testid="schedule-button"
      >
        <IconComponent name="Clock" className="!h-4 !w-4 mr-1.5" />
        Schedule
      </Button>
      <ScheduleModal
        open={openScheduleModal}
        setOpen={setOpenScheduleModal}
        flowId={flowId}
      />
    </>
  );
};

export default ScheduleButton;
