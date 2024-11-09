import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const GridSkeleton = () => {
  return (
    <Card className="my-1 flex flex-col rounded-lg border border-border bg-background p-4">
      <div className="flex w-full items-center gap-4">
        {/* Icon skeleton */}
        <div className="flex rounded-lg">
          <Skeleton className="h-[44px] w-[44px] rounded-lg" />
        </div>

        <div className="flex w-full min-w-0 items-center justify-between">
          <div className="flex min-w-0 flex-col gap-2">
            {/* Title skeleton */}
            <Skeleton className="h-5 w-[120px]" />
            {/* Time skeleton */}
            <Skeleton className="h-4 w-[150px]" />
          </div>
          {/* Dropdown button skeleton */}
          <Skeleton className="ml-2 h-10 w-10 rounded-md" />
        </div>
      </div>

      {/* Description skeleton */}
      <div className="pt-5">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="mt-2 h-4 w-3/4" />
      </div>
    </Card>
  );
};

export default GridSkeleton;
