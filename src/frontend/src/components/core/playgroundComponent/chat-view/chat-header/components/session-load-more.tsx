import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";

export interface SessionPaginationProps {
  hasMoreSessions?: boolean;
  isLoadingSessions?: boolean;
  onLoadMoreSessions?: () => void;
}

export function SessionLoadMore({
  hasMoreSessions,
  isLoadingSessions,
  onLoadMoreSessions,
}: SessionPaginationProps) {
  const { t } = useTranslation();
  if (!hasMoreSessions) return null;
  return (
    <Button
      type="button"
      variant="ghost"
      className="w-full"
      data-testid="load-more-sessions"
      disabled={isLoadingSessions}
      onClick={onLoadMoreSessions}
    >
      {t(isLoadingSessions ? "loading.loading" : "nodeToolbar.showMore")}
    </Button>
  );
}
