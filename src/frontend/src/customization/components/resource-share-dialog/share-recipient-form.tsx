import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useSearchAuthorizationRecipients } from "@/controllers/API/queries/authorization";
import { useCreateShare } from "@/controllers/API/queries/shares";
import type {
  AuthorizationRecipient,
  ShareDialogPermission,
  ShareRecipientType,
  ShareResourceType,
} from "@/types/authz";
import { extractApiErrorMessages } from "@/utils/apiError";
import { cn } from "@/utils/utils";
import {
  permissionDescriptionKey,
  permissionLabelKey,
  permissionOptions,
} from "./permission-options";

function useDebouncedValue(value: string, delay = 300): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [delay, value]);
  return debounced;
}

export function ShareRecipientForm({
  open,
  resourceType,
  resourceId,
}: {
  open: boolean;
  resourceType: ShareResourceType;
  resourceId: string;
}) {
  const { t } = useTranslation();
  const searchId = useId();
  const [recipientType, setRecipientType] =
    useState<ShareRecipientType>("user");
  const [search, setSearch] = useState("");
  const [selectedRecipient, setSelectedRecipient] =
    useState<AuthorizationRecipient | null>(null);
  const [permission, setPermission] =
    useState<ShareDialogPermission>("execute");
  const [error, setError] = useState<string | null>(null);
  const debouncedSearch = useDebouncedValue(search);
  const recipients = useSearchAuthorizationRecipients(
    {
      purpose: "share",
      kind: recipientType,
      query: debouncedSearch,
      resourceType,
      resourceId,
    },
    { enabled: open },
  );
  const createShare = useCreateShare({
    onSuccess: () => {
      setSearch("");
      setSelectedRecipient(null);
      setError(null);
    },
    onError: (requestError) =>
      setError(extractApiErrorMessages(requestError).join(" ")),
  });

  useEffect(() => {
    setSelectedRecipient(null);
    setSearch("");
  }, [recipientType]);

  useEffect(() => {
    setRecipientType("user");
    setSearch("");
    setSelectedRecipient(null);
    setPermission("execute");
    setError(null);
  }, [open, resourceId, resourceType]);

  return (
    <section aria-labelledby="share-recipient-heading" className="space-y-3">
      <h3 id="share-recipient-heading" className="text-sm font-semibold">
        {t("sharing.addRecipient")}
      </h3>
      <RadioGroup
        value={recipientType}
        onValueChange={(value) => setRecipientType(value as ShareRecipientType)}
        className="grid grid-cols-2"
        aria-label={t("sharing.recipientType")}
        // Let the selected radio define the dialog's first tab stop. The
        // roving-focus wrapper otherwise hides that edge from the focus trap
        // when Shift+Tab leaves the first radio.
        tabIndex={-1}
      >
        {(["user", "team"] as ShareRecipientType[]).map((kind) => (
          <Label
            key={kind}
            className="flex cursor-pointer items-center gap-2 rounded-md border p-3"
          >
            <RadioGroupItem
              value={kind}
              tabIndex={recipientType === kind ? 0 : -1}
            />
            {t(`sharing.recipient.${kind}`)}
          </Label>
        ))}
      </RadioGroup>

      <div className="space-y-1.5">
        <Label htmlFor={searchId}>{t("sharing.searchRecipients")}</Label>
        <Input
          id={searchId}
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setSelectedRecipient(null);
          }}
          placeholder={t("sharing.searchPlaceholder", {
            recipient: t(`sharing.recipient.${recipientType}`).toLowerCase(),
          })}
          aria-describedby={`${searchId}-hint`}
        />
        <p id={`${searchId}-hint`} className="text-xs text-muted-foreground">
          {t("sharing.searchHint")}
        </p>
      </div>

      {recipients.isFetching && debouncedSearch.trim().length >= 2 && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("sharing.searching")}
        </p>
      )}
      {recipients.data?.items && recipients.data.items.length > 0 && (
        <ul className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-1">
          {recipients.data.items.map((recipient) => (
            <li key={`${recipient.kind}-${recipient.id}`}>
              <button
                type="button"
                className={cn(
                  "w-full rounded px-3 py-2 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  selectedRecipient?.id === recipient.id && "bg-muted",
                )}
                aria-pressed={selectedRecipient?.id === recipient.id}
                onClick={() => setSelectedRecipient(recipient)}
              >
                {recipient.display_name}
              </button>
            </li>
          ))}
        </ul>
      )}

      <RadioGroup
        value={permission}
        onValueChange={(value) => setPermission(value as ShareDialogPermission)}
        className="grid grid-cols-1 gap-2 sm:grid-cols-2"
        aria-label={t("sharing.accessLevel")}
      >
        {permissionOptions.map((option) => (
          <Label
            key={option}
            className={cn(
              "flex cursor-pointer items-start gap-3 rounded-lg border p-3",
              permission === option && "border-primary",
            )}
          >
            <RadioGroupItem value={option} />
            <span>
              <span className="block text-sm font-medium">
                {t(permissionLabelKey(option))}
              </span>
              <span className="mt-1 block text-xs font-normal text-muted-foreground">
                {t(permissionDescriptionKey(option))}
              </span>
            </span>
          </Label>
        ))}
      </RadioGroup>

      {recipientType === "team" && selectedRecipient && (
        <p className="text-xs text-muted-foreground">
          {t("sharing.team.futureMembers")}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button
        type="button"
        className="w-full sm:w-auto"
        disabled={!selectedRecipient}
        loading={createShare.isPending}
        onClick={() => {
          if (!selectedRecipient) return;
          setError(null);
          createShare.mutate({
            resourceType,
            resourceId,
            recipientType,
            recipientId: selectedRecipient.id,
            permission,
          });
        }}
      >
        {t("sharing.save")}
      </Button>
    </section>
  );
}
