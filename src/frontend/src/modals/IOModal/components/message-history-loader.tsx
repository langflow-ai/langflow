import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import type { useGetMessageHistory } from "@/controllers/API/queries/messages/use-get-message-history";

export type MessageHistoryControls = Pick<
  ReturnType<typeof useGetMessageHistory>,
  | "hasNextPage"
  | "isFetching"
  | "isError"
  | "isFetchNextPageError"
  | "fetchNextPage"
  | "refetch"
  | "data"
>;

export function MessageHistoryLoader({
  history,
}: {
  history: MessageHistoryControls;
}) {
  const { t } = useTranslation();
  if (!history.hasNextPage && !history.isError) return null;

  return (
    <div className="flex shrink-0 flex-col items-center gap-2 py-2">
      {history.isError && <p role="alert">{t("messages.loadError")}</p>}
      <Button
        variant="outline"
        size="sm"
        data-testid="load-older-messages"
        disabled={history.isFetching}
        onClick={() => {
          if (history.isError && !history.isFetchNextPageError)
            void history.refetch();
          else void history.fetchNextPage();
        }}
      >
        {history.isFetching
          ? t("common.loading")
          : history.isError
            ? t("common.retry")
            : t("messages.loadOlder")}
      </Button>
    </div>
  );
}
