import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useIngestViaConnector } from "@/controllers/API/queries/knowledge-bases/use-ingest-via-connector";

interface S3ConnectorFormProps {
  kbName: string;
  onSubmitted?: () => void;
}

/**
 * Inline S3 ingestion form.
 *
 * Credentials are stored as Langflow variables, so the form only
 * asks for variable *names* — not the secrets themselves. A user
 * who hasn't configured the variables yet sees a 400 from the
 * backend on submit (S3Source.validate_config raises early).
 */
const S3ConnectorForm = ({ kbName, onSubmitted }: S3ConnectorFormProps) => {
  const [bucket, setBucket] = useState("");
  const [prefix, setPrefix] = useState("");
  const [accessKeyVariable, setAccessKeyVariable] =
    useState("AWS_ACCESS_KEY_ID");
  const [secretKeyVariable, setSecretKeyVariable] = useState(
    "AWS_SECRET_ACCESS_KEY",
  );
  const [regionVariable, setRegionVariable] = useState("");
  const [endpointUrlVariable, setEndpointUrlVariable] = useState("");

  const ingestMutation = useIngestViaConnector();
  const submitting = ingestMutation.isPending;
  const errorMessage = ingestMutation.error
    ? extractErrorDetail(ingestMutation.error)
    : null;

  const canSubmit = bucket.trim().length > 0 && !submitting;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    ingestMutation.mutate(
      {
        kb_name: kbName,
        source_type: "s3",
        source_config: {
          bucket: bucket.trim(),
          prefix: prefix.trim() || undefined,
          access_key_variable: accessKeyVariable.trim() || undefined,
          secret_key_variable: secretKeyVariable.trim() || undefined,
          region_variable: regionVariable.trim() || undefined,
          endpoint_url_variable: endpointUrlVariable.trim() || undefined,
        },
        source_name: `s3://${bucket.trim()}${prefix ? `/${prefix.trim()}` : ""}`,
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

      {errorMessage && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
          {errorMessage}
        </div>
      )}

      <div className="flex justify-end">
        <Button type="submit" disabled={!canSubmit} size="sm">
          {submitting ? "Starting…" : "Ingest from S3"}
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

export default S3ConnectorForm;
