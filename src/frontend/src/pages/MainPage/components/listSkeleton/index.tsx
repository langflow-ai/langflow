import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const ListSkeleton = () => {
  return (
    <Card className="my-2 flex flex-row justify-between rounded-lg border border-border bg-background p-4">
      {/* left side */}
      <div className="flex min-w-0 items-center gap-4">
        {/* Icon skeleton */}
        <div className="flex h-[52px] w-[52px] items-center justify-center rounded-lg">
          <Skeleton className="h-full w-full rounded-lg" />
        </div>

        <div className="flex min-w-0 flex-col justify-start gap-2">
          {/* Title and time skeleton */}
          <div className="flex min-w-0 items-baseline max-md:flex-col">
            <Skeleton className="h-5 w-[150px]" />
            <Skeleton className="ml-2 h-4 w-[180px]" />
          </div>
          {/* Description skeleton */}
          <Skeleton className="h-4 w-[250px]" />
        </div>
      </div>

      {/* right side */}
      <div className="ml-5 flex items-center gap-2">
        <Skeleton className="h-10 w-10 rounded-md" />
      </div>
    </Card>
  );
};

export default ListSkeleton;
