import { Trash2 } from "lucide-react";
import { useState } from "react";
import {
  useCreateScheduler,
  useDeleteScheduler,
  useGetSchedulers,
  useUpdateScheduler,
} from "../../hooks/scheduler/use-scheduler";
import useAlertStore from "../../stores/alertStore";
import { SchedulerType } from "../../types/scheduler";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";
import { Textarea } from "../ui/textarea";

interface SchedulerComponentProps {
  flowId: string;
}

export default function SchedulerComponent({
  flowId,
}: SchedulerComponentProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [intervalSeconds, setIntervalSeconds] = useState("60"); // Default to 60 seconds
  const [enabled, setEnabled] = useState(true);
  const [selectedScheduler, setSelectedScheduler] =
    useState<SchedulerType | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const {
    data: schedulers = [],
    isLoading,
    refetch,
  } = useGetSchedulers(flowId);
  const createSchedulerMutation = useCreateScheduler();
  const updateSchedulerMutation = useUpdateScheduler();
  const deleteSchedulerMutation = useDeleteScheduler();

  const handleSelectScheduler = (scheduler: SchedulerType) => {
    setSelectedScheduler(scheduler);
    setName(scheduler.name);
    setDescription(scheduler.description || "");
    setIntervalSeconds(scheduler.interval_seconds?.toString() || "60");
    setEnabled(scheduler.enabled);
    setIsEditing(true);
  };

  const handleCreateScheduler = async () => {
    try {
      const schedulerData = {
        name,
        description,
        flow_id: flowId,
        interval_seconds: parseInt(intervalSeconds),
        enabled,
      };

      await createSchedulerMutation.mutateAsync(schedulerData);
      setSuccessData({ title: "Scheduler created successfully" });
      resetForm();
      refetch();
    } catch (error) {
      console.error("Failed to create scheduler:", error);
      setErrorData({ title: "Error", list: ["Failed to create scheduler"] });
    }
  };

  const handleUpdateScheduler = async () => {
    if (!selectedScheduler) return;

    try {
      const schedulerData = {
        name,
        description,
        interval_seconds: parseInt(intervalSeconds),
        enabled,
      };

      await updateSchedulerMutation.mutateAsync({
        id: selectedScheduler.id,
        scheduler: schedulerData,
      });
      setSuccessData({ title: "Scheduler updated successfully" });
      resetForm();
      refetch();
    } catch (error) {
      console.error("Failed to update scheduler:", error);
      setErrorData({ title: "Error", list: ["Failed to update scheduler"] });
    }
  };

  const handleDeleteScheduler = async () => {
    if (!selectedScheduler) return;

    try {
      await deleteSchedulerMutation.mutateAsync(selectedScheduler.id);
      setSuccessData({ title: "Scheduler deleted successfully" });
      resetForm();
      refetch();
    } catch (error) {
      console.error("Failed to delete scheduler:", error);
      setErrorData({ title: "Error", list: ["Failed to delete scheduler"] });
    }
  };

  const resetForm = () => {
    setName("");
    setDescription("");
    setIntervalSeconds("60");
    setEnabled(true);
    setSelectedScheduler(null);
    setIsEditing(false);
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h3 className="text-lg font-medium">Schedulers</h3>
        <p className="text-sm text-muted-foreground">
          Configure schedulers to run your flow automatically.
        </p>
      </div>

      {schedulers.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="text-sm font-medium">Existing Schedulers</h4>
          <div className="grid gap-2">
            {schedulers.map((scheduler) => (
              <div
                key={scheduler.id}
                className={`flex cursor-pointer items-center justify-between rounded-md border p-2 ${
                  selectedScheduler?.id === scheduler.id ? "border-primary" : ""
                }`}
                onClick={() => handleSelectScheduler(scheduler)}
              >
                <div className="flex flex-col">
                  <span className="font-medium">{scheduler.name}</span>
                  <span className="text-xs text-muted-foreground">
                    Interval: {scheduler.interval_seconds} seconds
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1">
                    <div
                      className={`h-2 w-2 rounded-full ${
                        scheduler.enabled ? "bg-green-500" : "bg-red-500"
                      }`}
                    />
                    <span className="text-xs">
                      {scheduler.enabled ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-4 rounded-md border p-4">
        <h4 className="text-sm font-medium">
          {isEditing ? "Edit Scheduler" : "Create Scheduler"}
        </h4>

        <div className="grid gap-2">
          <Label htmlFor="name">Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Scheduler name"
          />
        </div>

        <div className="grid gap-2">
          <Label htmlFor="description">Description (optional)</Label>
          <Textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Scheduler description"
          />
        </div>

        <div className="grid gap-2">
          <Label htmlFor="intervalSeconds">Interval (seconds)</Label>
          <Input
            id="intervalSeconds"
            type="number"
            value={intervalSeconds}
            onChange={(e) => setIntervalSeconds(e.target.value)}
            placeholder="60"
          />
          <p className="text-xs text-muted-foreground">
            Time in seconds between each run (e.g., 3600 for every hour)
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Switch id="enabled" checked={enabled} onCheckedChange={setEnabled} />
          <Label htmlFor="enabled">Enabled</Label>
        </div>

        <div className="flex justify-between">
          <div className="flex gap-2">
            <Button
              onClick={
                isEditing ? handleUpdateScheduler : handleCreateScheduler
              }
              disabled={
                isLoading ||
                createSchedulerMutation.isPending ||
                updateSchedulerMutation.isPending ||
                deleteSchedulerMutation.isPending ||
                !name ||
                !intervalSeconds
              }
            >
              {isEditing ? "Update" : "Create"}
            </Button>
            {isEditing && (
              <Button variant="outline" onClick={resetForm}>
                Cancel
              </Button>
            )}
          </div>
          {isEditing && (
            <Button
              variant="destructive"
              size="icon"
              onClick={handleDeleteScheduler}
              disabled={
                isLoading ||
                createSchedulerMutation.isPending ||
                updateSchedulerMutation.isPending ||
                deleteSchedulerMutation.isPending
              }
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
