import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useIngestViaConnector } from "@/controllers/API/queries/knowledge-bases/use-ingest-via-connector";

interface SharePointConnectorFormProps {
  kbName: string;
  onSubmitted?: () => void;
}

/**
 * SharePoint ingestion form.
 *
 * Requires a ``site_id`` (fully-qualified Graph triple:
 * ``hostname,site-guid,web-guid``) - obtainable via one Graph call
 * to ``GET /sites/{hostname}:/{site-path}``. Document library is
 * the site's default drive unless ``drive_id`` is specified.
 */
const SharePointConnectorForm = ({
  kbName,
  onSubmitted,
}: SharePointConnectorFormProps) => {
  const [siteId, setSiteId] = useState("");
  const [driveId, setDriveId] = useState("");
  const [folderPath, setFolderPath] = useState("");
  const [recursive, setRecursive] = useState(true);
  const [clientIdVariable, setClientIdVariable] = useState(
    "MICROSOFT_OAUTH_CLIENT_ID",
  );
  const [clientSecretVariable, setClientSecretVariable] = useState(
    "MICROSOFT_OAUTH_CLIENT_SECRET",
  );
  const [refreshTokenVariable, setRefreshTokenVariable] = useState(
    "MICROSOFT_OAUTH_REFRESH_TOKEN",
  );
  const [tenantIdVariable, setTenantIdVariable] = useState(
    "MICROSOFT_OAUTH_TENANT_ID",
  );

  const ingestMutation = useIngestViaConnector();
  const submitting = ingestMutation.isPending;
  const errorMessage = ingestMutation.error
    ? extractErrorDetail(ingestMutation.error)
    : null;
  const canSubmit = siteId.trim().length > 0 && !submitting;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    ingestMutation.mutate(
      {
        kb_name: kbName,
        source_type: "sharepoint",
        source_config: {
          site_id: siteId.trim(),
          drive_id: driveId.trim() || undefined,
          folder_path: folderPath.trim() || undefined,
          recursive,
          client_id_variable: clientIdVariable.trim() || undefined,
          client_secret_variable: clientSecretVariable.trim() || undefined,
          refresh_token_variable: refreshTokenVariable.trim() || undefined,
          tenant_id_variable: tenantIdVariable.trim() || undefined,
        },
        source_name: `sharepoint:${siteId.trim()}${folderPath ? `/${folderPath}` : ""}`,
      },
      {
        onSuccess: () => {
          onSubmitted?.();
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <Field label="Site ID" required>
        <Input
          value={siteId}
          onChange={(e) => setSiteId(e.target.value)}
          placeholder="contoso.sharepoint.com,<site-guid>,<web-guid>"
          required
        />
      </Field>
      <Field label="Drive ID (optional)">
        <Input
          value={driveId}
          onChange={(e) => setDriveId(e.target.value)}
          placeholder="Leave blank to use the site's default drive"
        />
      </Field>
      <Field label="Folder path (optional)">
        <Input
          value={folderPath}
          onChange={(e) => setFolderPath(e.target.value)}
          placeholder="General"
        />
      </Field>
      <label className="flex items-center gap-2 text-xs font-medium">
        <input
          type="checkbox"
          checked={recursive}
          onChange={(e) => setRecursive(e.target.checked)}
        />
        Recurse into subfolders
      </label>
      <div className="grid grid-cols-1 gap-2">
        <Field label="Client ID variable">
          <Input
            value={clientIdVariable}
            onChange={(e) => setClientIdVariable(e.target.value)}
          />
        </Field>
        <Field label="Client Secret variable">
          <Input
            value={clientSecretVariable}
            onChange={(e) => setClientSecretVariable(e.target.value)}
          />
        </Field>
        <Field label="Refresh Token variable">
          <Input
            value={refreshTokenVariable}
            onChange={(e) => setRefreshTokenVariable(e.target.value)}
          />
        </Field>
        <Field label="Tenant ID variable">
          <Input
            value={tenantIdVariable}
            onChange={(e) => setTenantIdVariable(e.target.value)}
          />
        </Field>
      </div>

      {errorMessage && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
          {errorMessage}
        </div>
      )}

      <div className="flex justify-end">
        <Button type="submit" disabled={!canSubmit} size="sm">
          {submitting ? "Starting…" : "Ingest from SharePoint"}
        </Button>
      </div>
    </form>
  );
};

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">
        {label}
        {required ? " *" : ""}
      </span>
      {children}
    </label>
  );
}

function extractErrorDetail(error: Error): string {
  const response = (error as { response?: { data?: { detail?: unknown } } })
    ?.response;
  const detail = response?.data?.detail;
  if (typeof detail === "string") return detail;
  return error.message || "Ingestion failed.";
}

export default SharePointConnectorForm;
