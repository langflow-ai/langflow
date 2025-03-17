import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertCircle,
  CalendarClock,
  ListChecks,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import { useState } from "react";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../../components/ui/alert";
import { Button } from "../../../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../../components/ui/card";
import { Skeleton } from "../../../../components/ui/skeleton";
import {
  useGetSchedulers,
  useGetSchedulerStatus,
} from "../../../../hooks/scheduler/use-scheduler";
import SchedulerPageHeaderComponent from "./components/SchedulerPageHeader";
import SchedulerTable from "./components/SchedulerTable";
import StatusCard from "./components/StatusCard";

export default function SchedulerPage() {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const {
    data: schedulers = [],
    isLoading: isLoadingSchedulers,
    isError: isSchedulersError,
    error: schedulersError,
  } = useGetSchedulers();

  const {
    data: schedulerStatus,
    isLoading: isLoadingStatus,
    isError: isStatusError,
    error: statusError,
  } = useGetSchedulerStatus();

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["schedulers"] }),
        queryClient.invalidateQueries({ queryKey: ["scheduler-status"] }),
        queryClient.invalidateQueries({ queryKey: ["next-run-times"] }),
      ]);
    } catch (error) {
      console.error("Error refreshing data:", error);
    } finally {
      setTimeout(() => setIsRefreshing(false), 500);
    }
  };

  return (
    <div className="flex h-full flex-col space-y-4 p-4">
      <div className="flex items-center justify-between">
        <SchedulerPageHeaderComponent />
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="transition-all duration-200 ease-in-out"
        >
          {isRefreshing ? (
            <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          {isRefreshing ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      {(isSchedulersError || isStatusError) && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            {isSchedulersError &&
              `Failed to load schedulers: ${schedulersError?.message || "Unknown error"}`}
            {isStatusError &&
              `Failed to load scheduler status: ${statusError?.message || "Unknown error"}`}
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <StatusCard
          title="Scheduler Status"
          value={
            schedulerStatus?.service_status === "running"
              ? "Running"
              : "Stopped"
          }
          icon={Activity}
          description="The scheduler service is responsible for running flows at scheduled times."
          variant={
            schedulerStatus?.service_status === "running"
              ? "success"
              : "destructive"
          }
          isLoading={isLoadingStatus}
        />
        <StatusCard
          title="Active Schedulers"
          value={schedulerStatus?.job_count?.toString() || "0"}
          icon={CalendarClock}
          description="Number of active scheduled jobs."
          variant="default"
          isLoading={isLoadingStatus}
        />
        <StatusCard
          title="Total Schedulers"
          value={schedulers.length.toString()}
          icon={ListChecks}
          description="Total number of schedulers configured."
          variant="default"
          isLoading={isLoadingSchedulers}
        />
      </div>

      <div className="flex-1 space-y-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Schedulers</CardTitle>
              <CardDescription>
                Manage your scheduled flows. Enable, disable, or delete
                schedulers.
              </CardDescription>
            </div>
            {isLoadingSchedulers && (
              <LoaderCircle className="h-5 w-5 animate-spin text-muted-foreground" />
            )}
          </CardHeader>
          <CardContent>
            {isLoadingSchedulers && schedulers.length === 0 ? (
              <div className="space-y-2">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : (
              <SchedulerTable
                schedulers={schedulers}
                onRefresh={handleRefresh}
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
