import { useState } from "react";
import { useTranslation } from "react-i18next";
import { BASE_URL_API } from "@/customization/config-constants";
import type { CollaborationSelectionParticipant } from "@/hooks/flows/collaboration-selection-markers";
import { cn } from "@/utils/utils";

type CollaborationSelectionBumpProps = {
  participants: CollaborationSelectionParticipant[];
  className?: string;
};

function profileImageUrl(profileImage?: string | null): string {
  return `${BASE_URL_API}files/profile_pictures/${
    profileImage ?? "Space/046-rocket.svg"
  }`;
}

export default function CollaborationSelectionBump({
  participants,
  className,
}: CollaborationSelectionBumpProps): JSX.Element | null {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  if (participants.length === 0) {
    return null;
  }

  const uniqueParticipants = participants.filter(
    (participant, index, list) =>
      list.findIndex((entry) => entry.user_id === participant.user_id) ===
      index,
  );
  const visibleParticipants = uniqueParticipants.slice(0, 3);
  const overflowCount = uniqueParticipants.length - visibleParticipants.length;
  const outlineColors = uniqueParticipants.map(
    (participant) => participant.color,
  );

  const bumpSurfaceStyle = {
    borderColor: outlineColors[0],
    boxShadow:
      outlineColors.length > 1
        ? outlineColors
            .map((color, index) => `0 0 0 ${1 + index}px ${color}40`)
            .join(", ")
        : undefined,
  };

  return (
    <div
      className={cn("relative inline-flex", className)}
      data-testid="collaboration-selection-bump"
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      onFocus={() => setExpanded(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setExpanded(false);
        }
      }}
    >
      <div
        className={cn(
          "flex items-center rounded-full border bg-background px-0.5 py-0.5 shadow-md transition-opacity duration-200",
          expanded && "opacity-0",
        )}
        style={bumpSurfaceStyle}
        aria-hidden={expanded}
      >
        <div className="flex items-center pl-0.5">
          {visibleParticipants.map((participant) => (
            <img
              key={participant.user_id}
              src={profileImageUrl(participant.profile_image)}
              alt={participant.username}
              title={
                participant.isCurrentUser
                  ? t("flow.collaboration.you", { defaultValue: "You" })
                  : participant.username
              }
              className={cn(
                "h-6 w-6 rounded-full border-2 object-cover",
                participant !== visibleParticipants[0] && "-ml-2.5",
              )}
              style={{
                borderColor: participant.color,
                backgroundColor: "hsl(var(--background))",
              }}
              data-testid={`collaboration-selection-bump-avatar-${participant.user_id}`}
            />
          ))}
          {overflowCount > 0 ? (
            <span className="-ml-2 flex h-6 w-6 items-center justify-center rounded-full border-2 border-background bg-muted text-[9px] font-semibold text-muted-foreground">
              +{overflowCount}
            </span>
          ) : null}
        </div>
      </div>
      {expanded ? (
        <div
          className="absolute left-0 top-1/2 z-[70] min-w-max -translate-y-1/2 rounded-full border bg-background px-1.5 py-1 shadow-lg"
          style={bumpSurfaceStyle}
        >
          <div className="flex max-w-[220px] flex-col gap-1">
            {uniqueParticipants.map((participant) => (
              <div
                key={participant.user_id}
                className="flex min-w-0 items-center gap-1.5 rounded-full px-1 py-0.5"
                data-testid={`collaboration-selection-bump-user-${participant.user_id}`}
              >
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: participant.color }}
                />
                <img
                  src={profileImageUrl(participant.profile_image)}
                  alt={participant.username}
                  className="h-5 w-5 shrink-0 rounded-full border-2 object-cover"
                  style={{
                    borderColor: participant.color,
                    backgroundColor: "hsl(var(--background))",
                  }}
                />
                <span className="truncate text-[11px] font-medium">
                  {participant.isCurrentUser
                    ? t("flow.collaboration.you", { defaultValue: "You" })
                    : participant.username}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
