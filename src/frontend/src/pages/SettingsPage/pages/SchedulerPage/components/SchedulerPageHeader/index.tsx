import { Clock } from "lucide-react";

const SchedulerPageHeaderComponent = () => {
  return (
    <>
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            Schedulers
            <Clock
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Manage scheduled tasks for your flows.
          </p>
        </div>
      </div>
    </>
  );
};

export default SchedulerPageHeaderComponent; 