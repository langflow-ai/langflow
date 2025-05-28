import { cn } from "@/utils/utils";

export function DotBackgroundDemo({
  children,
  className,
  containerClassName,
}: {
  children: React.ReactNode;
  className?: string;
  containerClassName?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex h-full w-full items-center justify-center bg-background",
        className,
      )}
    >
      <div
        className={cn(
          "absolute inset-0",
          "[background-size:20px_20px]",
          "[background-image:radial-gradient(#d4d4d4_1px,transparent_1px)]",
          "dark:[background-image:radial-gradient(#404040_1px,transparent_1px)]",
        )}
      />
      <div
        className={cn(
          "absolute inset-0 bg-gradient-to-b from-background/0 from-0% via-background/50 via-30% to-background to-50%",
          containerClassName,
        )}
      />
      {children}
    </div>
  );
}
