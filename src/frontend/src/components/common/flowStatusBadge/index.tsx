import { cn } from "@/utils/utils";
import { useState } from "react";
import IconComponent from "../genericIconComponent";
import ShadTooltip from "../shadTooltipComponent";

export type FlowStatus =
  | "Draft"
  | "Submitted"
  | "Approved"
  | "Rejected"
  | "Published"
  | "Unpublished"
  | "Deleted"
  | null;

interface FlowStatusBadgeProps {
  status: FlowStatus;
  className?: string;
  rejectionReason?: string | null;
}

const statusConfig: Record<
  NonNullable<FlowStatus>,
  { label: string; className: string }
> = {
  Draft: {
    label: "Draft",
    className: "bg-gray-100 text-gray-700 border-gray-300",
  },
  Submitted: {
    label: "Under Review",
    className: "bg-yellow-100 text-yellow-800 border-yellow-300",
  },
  Approved: {
    label: "Approved",
    className: "bg-green-100 text-green-800 border-green-300",
  },
  Rejected: {
    label: "Rejected",
    className: "bg-red-100 text-red-800 border-red-300",
  },
  Published: {
    label: "Published",
    className: "bg-blue-100 text-blue-800 border-blue-300",
  },
  Unpublished: {
    label: "Unpublished",
    className: "bg-gray-100 text-gray-600 border-gray-300",
  },
  Deleted: {
    label: "Deleted",
    className: "bg-red-50 text-red-600 border-red-200",
  },
};

export function FlowStatusBadge({ status, className, rejectionReason }: FlowStatusBadgeProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  if (!status) {
    // Show Draft badge for flows with no submissions
    return (
      <span
        className={cn(
          "ml-2 inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
          statusConfig.Draft.className,
          className
        )}
      >
        {statusConfig.Draft.label}
      </span>
    );
  }

  const config = statusConfig[status];
  const isRejected = status === "Rejected";
  const hasRejectionReason = isRejected && rejectionReason;

  if (hasRejectionReason) {
    return (
      <ShadTooltip
        content={rejectionReason}
        side="bottom"
        open={showTooltip}
        setOpen={setShowTooltip}
        delayDuration={0}
      >
        <span
          onClick={(e) => {
            e.stopPropagation();
            setShowTooltip(!showTooltip);
          }}
          className={cn(
            "ml-2 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium cursor-pointer",
            config.className,
            className
          )}
        >
          {config.label}
          <IconComponent
            name="Info"
            className="h-3.5 w-3.5"
          />
        </span>
      </ShadTooltip>
    );
  }

  return (
    <span
      className={cn(
        "ml-2 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        config.className,
        className
      )}
    >
      {config.label}
    </span>
  );
}

export default FlowStatusBadge;
