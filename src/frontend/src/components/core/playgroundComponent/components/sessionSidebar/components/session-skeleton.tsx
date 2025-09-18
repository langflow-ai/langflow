import { Skeleton } from "@/components/ui/skeleton";

export const SessionSkeleton = () => {
  return (
    <div className="flex flex-col gap-1">
      <div className="w-full flex items-center px-3 h-8 bg-muted rounded-md">
        <Skeleton className="w-20 h-2" />
      </div>
      <div className="w-full flex items-center px-3 h-8">
        <Skeleton className="w-24 h-2" />
      </div>
      <div className="w-full flex items-center px-3 h-8">
        <Skeleton className="w-20 h-2" />
      </div>
    </div>
  );
};
