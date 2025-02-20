import { Skeleton } from "@/components/ui/skeleton";

const SkeletonGroup = ({
  count = 2,
  containerClassName = "flex flex-col gap-3 px-4 pt-4",
}: {
  count?: number;
  containerClassName?: string;
}) => {
  return (
    <div className={containerClassName}>
      {Array(count)
        .fill(null)
        .map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
    </div>
  );
};

export default SkeletonGroup;
