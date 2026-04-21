import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useIngestViaConnector } from "@/controllers/API/queries/knowledge-bases/use-ingest-via-connector";
import type { DeferredConnectorPayload } from "./connectorPayload";

interface S3ConnectorFormProps {
  kbName?: string;
  onSubmitted?: () => void;
  /**
   * Deferred mode: when provided, the form stops self-submitting
   * and emits its validated payload upward on every change (or
   * ``null`` if required fields are missing). The parent owns the
   * actual ingestion dispatch. Used by the unified create-KB modal
   * where the KB doesn't exist yet at the time the user is filling
   * out source config.
   */
  onPayloadChange?: (payload: DeferredConnectorPayload | null) => void;
}

/**
 * Inline S3 ingestion form.
 *
 * Credentials are stored as Langflow variables, so the form only
 * asks for variable *names* — not the secrets themselves. A user
 * who hasn't configured the variables yet sees a 400 from the
 * backend on submit (S3Source.validate_config raises early).
 */
const S3ConnectorForm = ({
  kbName,
  onSubmitted,
  onPayloadChange,
}: S3ConnectorFormProps) => {
  const [bucket, setBucket] = useState("");
  const [prefix, setPrefix] = useState("");
  const [accessKeyVariable, setAccessKeyVariable] =
    useState("AWS_ACCESS_KEY_ID");
  const [secretKeyVariable, setSecretKeyVariable] = useState(
    "AWS_SECRET_ACCESS_KEY",
  );
  const [regionVariable, setRegionVariable] = useState("");
  const [endpointUrlVariable, setEndpointUrlVariable] = useState("");

  const deferred = typeof onPayloadChange === "function";

  const ingestMutation = useIngestViaConnector();
  const submitting = ingestMutation.isPending;
  const errorMessage = ingestMutation.error
    ? extractErrorDetail(ingestMutation.error)
    : null;

  const canSubmit = bucket.trim().length > 0 && !submitting;

  const buildPayload = (): DeferredConnectorPayload | null => {
    const trimmedBucket = bucket.trim();
    if (!trimmedBucket) return null;
    return {
      source_type: "s3",
      source_config: {
        bucket: trimmedBucket,
        prefix: prefix.trim() || undefined,
        access_key_variable: accessKeyVariable.trim() || undefined,
        secret_key_variable: secretKeyVariable.trim() || undefined,
        region_variable: regionVariable.trim() || undefined,
        endpoint_url_variable: endpointUrlVariable.trim() || undefined,
      },
      source_name: `s3://${trimmedBucket}${prefix ? `/${prefix.trim()}` : ""}`,
    };
  };

  useEffect(() => {
    if (deferred) {
      onPayloadChange?.(buildPayload());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    deferred,
    bucket,
    prefix,
    accessKeyVariable,
    secretKeyVariable,
    regionVariable,
    endpointUrlVariable,
  ]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!kbName) return;
    const payload = buildPayload();
    if (!payload) return;
    ingestMutation.mutate(
      { kb_name: kbName, ...payload },
      { onSuccess: () => onSubmitted?.() },
    );
  };

  return (
    <form
      onSubmit={deferred ? (e) => e.preventDefault() : handleSubmit}
      className="flex flex-col gap-3"
    >
      <Field label="Bucket" required>
        <Input
          value={bucket}
          onChange={(e) => setBucket(e.target.value)}
          placeholder="my-bucket"
          required
          data-testid="s3-bucket-input"
        />
      </Field>
      <Field label="Prefix (optional)">
        <Input
          value={prefix}
          onChange={(e) => setPrefix(e.target.value)}
          placeholder="docs/"
        />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Access Key variable">
          <Input
            value={accessKeyVariable}
            onChange={(e) => setAccessKeyVariable(e.target.value)}
          />
        </Field>
        <Field label="Secret Key variable">
          <Input
            value={secretKeyVariable}
            onChange={(e) => setSecretKeyVariable(e.target.value)}
          />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Region variable (optional)">
          <Input
            value={regionVariable}
            onChange={(e) => setRegionVariable(e.target.value)}
            placeholder="AWS_REGION"
          />
        </Field>
        <Field label="Endpoint URL variable (S3-compatible)">
          <Input
            value={endpointUrlVariable}
            onChange={(e) => setEndpointUrlVariable(e.target.value)}
            placeholder="S3_ENDPOINT_URL"
          />
        </Field>
      </div>

      {!deferred && errorMessage && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
          {errorMessage}
        </div>
      )}

      {!deferred && (
        <div className="flex justify-end">
          <Button type="submit" disabled={!canSubmit} size="sm">
            {submitting ? "Starting…" : "Ingest from S3"}
          </Button>
        </div>
      )}
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

export default S3ConnectorForm;
