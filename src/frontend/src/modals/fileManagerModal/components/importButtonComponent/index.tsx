import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import { useState } from "react";

export default function ImportButtonComponent({}: {}) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <>
      <div
        className={cn(
          "relative flex h-10 w-fit select-none flex-col items-center justify-center whitespace-nowrap transition-all",
          isOpen ? "w-40" : "w-36",
        )}
      >
        <div
          className={cn(
            "absolute right-0 top-0 z-50 flex w-full flex-col items-start overflow-hidden rounded-md bg-primary text-sm font-semibold text-primary-foreground transition-all",
            isOpen ? "h-36" : "h-10 hover:bg-primary-hover",
          )}
        >
          <div
            className={cn(
              "flex h-10 w-full shrink-0 cursor-pointer items-center justify-between gap-2 px-3 transition-all",
            )}
            onClick={() => setIsOpen(!isOpen)}
          >
            Import from...
            <div className="flex h-4 w-4 items-center justify-center">
              <ForwardedIconComponent
                name="ChevronDown"
                className={cn(
                  "absolute h-4 w-4 transition-all",
                  isOpen && "opacity-0",
                )}
              />
              <ForwardedIconComponent
                name="X"
                className={cn(
                  "absolute h-4 w-4 opacity-0 transition-all",
                  isOpen && "opacity-100",
                )}
              />
            </div>
          </div>
          <div className="flex w-full flex-col gap-0 px-2 font-medium">
            <div className="relative flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-primary-hover">
              <ForwardedIconComponent name="GoogleDrive" className="h-4 w-4" />
              Drive
            </div>
            <div className="relative flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-primary-hover">
              <ForwardedIconComponent name="OneDrive" className="h-4 w-4" />
              OneDrive
            </div>
            <div className="relative flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-primary-hover">
              <ForwardedIconComponent name="AWSInverted" className="h-4 w-4" />
              S3 Bucket
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
