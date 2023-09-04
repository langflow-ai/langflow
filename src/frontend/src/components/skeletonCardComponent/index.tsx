import { Skeleton } from "../ui/skeleton";

export const SkeletonCardComponent = (): JSX.Element => {
  return (
    <div className="skeleton-card">
      <div className="skeleton-card-wrapper">
        <Skeleton className="h-8 w-8 rounded-full" />
        <Skeleton className="h-4 w-[120px]" />
      </div>
      <div className="skeleton-card-text">
        <Skeleton className="h-3 w-[250px]" />
        <Skeleton className="h-3 w-[200px]" />
      </div>
    </div>
  );
};
