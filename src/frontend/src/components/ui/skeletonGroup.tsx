import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/utils/utils";

const SkeletonGroup = ({
  count = 2,
  className = "",
}: {
  count?: number;
  className?: string;
}) => {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className={cn("w-full", className)} />
      ))}
    </>
  );
};

export default SkeletonGroup;
