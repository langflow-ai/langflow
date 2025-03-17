import { useState } from "react";
import {
  useDeleteScheduler,
  useGetNextRunTimes,
  useUpdateScheduler,
} from "../../../../../../hooks/scheduler/use-scheduler";
import { SchedulerType } from "../../../../../../types/scheduler";
import { Button } from "../../../../../../components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../../../../components/ui/table";
import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";
import { formatDistanceToNow, parseISO } from "date-fns";
import { Badge } from "../../../../../../components/ui/badge";
import { Switch } from "../../../../../../components/ui/switch";
import useAlertStore from "../../../../../../stores/alertStore";
import { SAVE_ERROR_ALERT, SAVE_SUCCESS_ALERT } from "../../../../../../constants/alerts_constants";
import { 
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../../../../../components/ui/alert-dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../../../../../../components/ui/tooltip";

interface SchedulerTableProps {
  schedulers: SchedulerType[];
  onRefresh?: () => void;
}

export default function SchedulerTable({ schedulers, onRefresh }: SchedulerTableProps) {
  const { data: nextRunTimes = [], isLoading: isLoadingNextRunTimes } = useGetNextRunTimes();
  const { mutateAsync: updateScheduler } = useUpdateScheduler();
  const { mutateAsync: deleteScheduler } = useDeleteScheduler();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [schedulerToDelete, setSchedulerToDelete] = useState<string | null>(null);

  // Create a map of scheduler IDs to next run times
  const nextRunTimeMap = nextRunTimes.reduce((acc, item) => {
    acc[item.scheduler_id] = item;
    return acc;
  }, {});

  const handleToggleEnabled = async (scheduler: SchedulerType) => {
    try {
      setLoading((prev) => ({ ...prev, [scheduler.id]: true }));
      await updateScheduler({
        id: scheduler.id,
        scheduler: { enabled: !scheduler.enabled },
      });
      setSuccessData(SAVE_SUCCESS_ALERT);
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error("Error toggling scheduler:", error);
      setErrorData(SAVE_ERROR_ALERT);
    } finally {
      setLoading((prev) => ({ ...prev, [scheduler.id]: false }));
    }
  };

  const confirmDeleteScheduler = (id: string) => {
    setSchedulerToDelete(id);
  };

  const handleDeleteScheduler = async () => {
    if (!schedulerToDelete) return;
    
    try {
      setLoading((prev) => ({ ...prev, [schedulerToDelete]: true }));
      await deleteScheduler(schedulerToDelete);
      setSuccessData({ title: "Success", list: ["Scheduler deleted successfully"] });
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error("Error deleting scheduler:", error);
      setErrorData(SAVE_ERROR_ALERT);
    } finally {
      setLoading((prev) => ({ ...prev, [schedulerToDelete]: false }));
      setSchedulerToDelete(null);
    }
  };

  const formatNextRunTime = (schedulerId: string) => {
    if (isLoadingNextRunTimes) {
      return "Loading...";
    }
    
    const nextRunInfo = nextRunTimeMap[schedulerId];
    if (!nextRunInfo || !nextRunInfo.next_run_time) {
      return "Not scheduled";
    }
    try {
      const nextRunDate = parseISO(nextRunInfo.next_run_time);
      return formatDistanceToNow(nextRunDate, { addSuffix: true });
    } catch (error) {
      return nextRunInfo.next_run_time || "Not scheduled";
    }
  };

  const getScheduleDescription = (scheduler: SchedulerType) => {
    if (scheduler.cron_expression) {
      return `Cron: ${scheduler.cron_expression}`;
    } else if (scheduler.interval_seconds) {
      return `Every ${scheduler.interval_seconds} seconds`;
    }
    return "No schedule set";
  };

  return (
    <TooltipProvider>
      <>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[200px]">Name</TableHead>
                <TableHead>Flow</TableHead>
                <TableHead>Schedule</TableHead>
                <TableHead>Next Run</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {schedulers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center">
                    No schedulers found
                  </TableCell>
                </TableRow>
              ) : (
                schedulers.map((scheduler) => (
                  <TableRow key={scheduler.id}>
                    <TableCell className="font-medium">{scheduler.name}</TableCell>
                    <TableCell className="max-w-[150px] truncate" title={scheduler.flow_id}>
                      {scheduler.flow_id}
                    </TableCell>
                    <TableCell>{getScheduleDescription(scheduler)}</TableCell>
                    <TableCell>{formatNextRunTime(scheduler.id)}</TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Switch
                              checked={scheduler.enabled}
                              disabled={loading[scheduler.id]}
                              onCheckedChange={() => handleToggleEnabled(scheduler)}
                            />
                          </TooltipTrigger>
                          <TooltipContent>
                            {scheduler.enabled ? "Disable scheduler" : "Enable scheduler"}
                          </TooltipContent>
                        </Tooltip>
                        <Badge
                          variant={scheduler.enabled ? "success" : "secondary"}
                        >
                          {scheduler.enabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => confirmDeleteScheduler(scheduler.id)}
                            disabled={loading[scheduler.id]}
                          >
                            {loading[scheduler.id] ? (
                              <ForwardedIconComponent
                                name="Loader2"
                                className="h-4 w-4 animate-spin"
                              />
                            ) : (
                              <ForwardedIconComponent
                                name="Trash"
                                className="h-4 w-4 text-destructive"
                              />
                            )}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Delete scheduler</TooltipContent>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        <AlertDialog open={!!schedulerToDelete} onOpenChange={(open) => !open && setSchedulerToDelete(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Are you sure?</AlertDialogTitle>
              <AlertDialogDescription>
                This action cannot be undone. This will permanently delete the scheduler.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleDeleteScheduler}>Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </>
    </TooltipProvider>
  );
} 