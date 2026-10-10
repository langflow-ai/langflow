import { useTranslation } from "react-i18next";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type MigrationState,
  type MigrationStepState,
  useVerifySecretKeyMutation,
} from "@/controllers/API/queries/migration";

// Prints the first 12 characters of the key's SHA-256, which the server compares with its own key's.
const FINGERPRINT_COMMAND = `printf '%s' "$LANGFLOW_SECRET_KEY" | sha256sum | cut -c1-12`;
const FIELD = "migration-key-fingerprint";

/**
 * The body of "Hand over the secret key". The admin sets this instance's key on the new instance,
 * then proves it with a fingerprint. The key itself never enters this page.
 */
export function SecretKeyStep({
  migration,
  state,
}: {
  migration: MigrationState;
  state: MigrationStepState;
}) {
  const { t } = useTranslation();
  const verify = useVerifySecretKeyMutation();
  const key = migration.instance.secret_key;
  const refusal = verify.error?.response?.data?.detail?.code;
  // A request that failed says nothing about the key, so the last answer is not shown as its outcome.
  const failed = verify.isError && refusal !== "fingerprint_mismatch";
  // The server keeps the last answer, so a mismatch still shows after a reload.
  const mismatch =
    !failed &&
    (state.reason === "fingerprint_mismatch" ||
      refusal === "fingerprint_mismatch");

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        const pasted = new FormData(event.currentTarget).get("fingerprint");
        verify.mutate(String(pasted));
      }}
    >
      <Alert variant="destructive" role="note">
        <AlertDescription>
          {t("settings.migration.key.warning", {
            step: t("settings.migration.step.start.title"),
          })}
        </AlertDescription>
      </Alert>
      <p className="break-words text-sm">
        {key?.source === "file"
          ? t("settings.migration.key.whereFile", { path: key.path })
          : t("settings.migration.key.whereEnv")}{" "}
        {t("settings.migration.key.set")}
      </p>
      <div className="flex flex-col gap-2">
        <p className="text-sm">{t("settings.migration.key.verifyIntro")}</p>
        <pre
          lang="en"
          className="select-all whitespace-pre-wrap break-words rounded-md bg-muted p-2 font-mono text-xs"
        >
          {FINGERPRINT_COMMAND}
        </pre>
        <p className="text-xs text-muted-foreground">
          {t("settings.migration.key.macNote")}
        </p>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor={FIELD}>{t("settings.migration.key.paste")}</Label>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
          <div className="flex-1">
            <Input
              id={FIELD}
              name="fingerprint"
              className="font-mono aria-[invalid=true]:border-destructive"
              spellCheck={false}
              required
              // No room for a pasted key.
              maxLength={12}
              aria-invalid={mismatch}
              aria-describedby={mismatch ? `${FIELD}-error` : undefined}
            />
          </div>
          <Button
            type="submit"
            className="w-full shrink-0 sm:w-fit"
            loading={verify.isPending}
            ignoreTitleCase
          >
            {t("settings.migration.key.action")}
          </Button>
        </div>
        {failed || mismatch ? (
          <p
            id={`${FIELD}-error`}
            role="alert"
            className="text-sm text-destructive"
          >
            {mismatch
              ? t("settings.migration.key.mismatch")
              : t("settings.migration.failed")}
          </p>
        ) : null}
      </div>
    </form>
  );
}
