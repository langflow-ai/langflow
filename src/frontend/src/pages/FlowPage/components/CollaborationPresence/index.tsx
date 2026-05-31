import { useTranslation } from "react-i18next";
import { BASE_URL_API } from "@/customization/config-constants";
import type { CollaborationPresenceUser } from "@/types/flow-collaboration";
import { cn } from "@/utils/utils";

type CollaborationPresenceProps = {
  users: CollaborationPresenceUser[];
  currentUserId?: string | null;
  className?: string;
};

function profileImageUrl(profileImage?: string | null): string {
  return `${BASE_URL_API}files/profile_pictures/${
    profileImage ?? "Space/046-rocket.svg"
  }`;
}

export default function CollaborationPresence({
  users,
  currentUserId,
  className,
}: CollaborationPresenceProps): JSX.Element | null {
  const { t } = useTranslation();

  const collaborators = users.filter((user) => user.user_id !== currentUserId);

  if (collaborators.length === 0) {
    return null;
  }

  const visibleUsers = collaborators.slice(0, 5);
  const overflowCount = collaborators.length - visibleUsers.length;

  return (
    <div
      className={cn("flex items-center gap-2", className)}
      data-testid="collaboration-presence"
      title={t("flow.collaboration.activeCollaborators", {
        count: collaborators.length,
        defaultValue: "{{count}} collaborators editing",
      })}
    >
      <span className="text-xs text-muted-foreground">
        {t("flow.collaboration.editing", { defaultValue: "Editing" })}
      </span>
      <div className="flex -space-x-2">
        {visibleUsers.map((user) => (
          <img
            key={user.user_id}
            src={profileImageUrl(user.profile_image)}
            alt={user.username}
            title={user.username}
            className="h-7 w-7 rounded-full border-2 border-background object-cover"
            data-testid={`collaboration-presence-user-${user.user_id}`}
          />
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
    </div>
  );
}
