import { Skeleton } from "@/components/ui/skeleton";

export function SidebarFolderSkeleton() {
  return (
    <div className="flex h-10 w-full shrink-0 animate-pulse cursor-pointer items-center gap-4 rounded-md border bg-background px-4 opacity-100 lg:min-w-full">
      <Skeleton className="h-3 w-4 rounded-full" />
      <Skeleton className="h-3 w-[40%]" />
    </div>
  );
}
