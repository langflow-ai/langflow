import { useTranslation } from "react-i18next";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { BASE_URL_API } from "@/customization/config-constants";
import type {
  CollaborationCollaboratorRow,
  CollaborationConnectionStatus,
} from "@/types/flow-collaboration";
import { cn } from "@/utils/utils";

type CollaborationPresenceAvatarsProps = {
  collaborators: CollaborationCollaboratorRow[];
  connectionStatus: CollaborationConnectionStatus;
  className?: string;
};

function profileImageUrl(profileImage?: string | null): string {
  return `${BASE_URL_API}files/profile_pictures/${
    profileImage ?? "Space/046-rocket.svg"
  }`;
}

function collaboratorTooltip(
  user: CollaborationCollaboratorRow,
  t: (
    key: string,
    options?: { defaultValue?: string; label?: string },
  ) => string,
): string {
  const displayName = user.isCurrentUser
    ? t("flow.collaboration.you", { defaultValue: "You" })
    : user.username;

  if (!user.selectionLabel) {
    return displayName;
  }

  if (user.selected?.kind === "edge") {
    return `${displayName}\n${t("flow.collaboration.selectedEdge", {
      label: user.selectionLabel,
      defaultValue: "Selected edge: {{label}}",
    })}`;
  }

  return `${displayName}\n${t("flow.collaboration.selectedNode", {
    label: user.selectionLabel,
    defaultValue: "Selected node: {{label}}",
  })}`;
}

function connectionStatusMessage(
  status: CollaborationConnectionStatus,
  t: (key: string, options?: { defaultValue?: string }) => string,
): string {
  switch (status) {
    case "connecting":
      return t("flow.collaboration.connecting", {
        defaultValue: "Connecting to collaboration…",
      });
    case "ready":
      return t("flow.collaboration.connectingPresence", {
        defaultValue: "Loading collaborators…",
      });
    case "disconnected":
      return t("flow.collaboration.disconnected", {
        defaultValue: "Collaboration disconnected. Edits may not sync.",
      });
    case "error":
      return t("flow.collaboration.connectionError", {
        defaultValue: "Collaboration connection error. Try reloading the flow.",
      });
    default:
      return t("flow.collaboration.starting", {
        defaultValue: "Starting collaboration…",
      });
  }
}

export default function CollaborationPresenceAvatars({
  collaborators,
  connectionStatus,
  className,
}: CollaborationPresenceAvatarsProps): JSX.Element | null {
  const { t } = useTranslation();

  if (collaborators.length === 0) {
    if (connectionStatus === "ready") {
      return null;
    }

    return (
      <div
        className={cn("flex items-center", className)}
        data-testid="collaboration-presence"
      >
        <span
          className="h-2 w-2 animate-pulse rounded-full bg-warning"
          title={connectionStatusMessage(connectionStatus, t)}
          data-testid="collaboration-presence-status"
        />
      </div>
    );
  }

  const visibleCollaborators = collaborators.slice(0, 4);
  const overflowCount = collaborators.length - visibleCollaborators.length;

  return (
    <div
      className={cn("flex items-center", className)}
      data-testid="collaboration-presence"
      title={t("flow.collaboration.activeCollaborators", {
        count: collaborators.length,
        defaultValue: "{{count}} collaborators editing",
      })}
    >
      <div className="flex items-center -space-x-1.5">
        {visibleCollaborators.map((user) => (
          <ShadTooltip
            key={user.user_id}
            content={collaboratorTooltip(user, t)}
            side="bottom"
          >
            <img
              src={profileImageUrl(user.profile_image)}
              alt={
                user.isCurrentUser
                  ? t("flow.collaboration.you", { defaultValue: "You" })
                  : user.username
              }
              className={cn(
                "h-7 w-7 rounded-full border-2 object-cover",
                connectionStatus !== "ready" && "opacity-60",
              )}
              style={{
                borderColor: user.color,
                backgroundColor: "hsl(var(--background))",
                boxShadow: user.isCurrentUser
                  ? `0 0 0 2px color-mix(in srgb, ${user.color} 35%, transparent)`
                  : undefined,
              }}
              data-testid={`collaboration-presence-user-${user.user_id}`}
            />
          </ShadTooltip>
        ))}
        {overflowCount > 0 ? (
          <span
            className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-background bg-muted text-[10px] font-medium text-muted-foreground"
            data-testid="collaboration-presence-overflow"
          >
            +{overflowCount}
          </span>
        ) : null}
      </div>
      {connectionStatus !== "ready" ? (
        <span
          className="ml-1.5 h-2 w-2 animate-pulse rounded-full bg-warning"
          data-testid="collaboration-presence-status"
          title={connectionStatusMessage(connectionStatus, t)}
        />
      ) : null}
    </div>
  );
}
