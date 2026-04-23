import * as Form from "@radix-ui/react-form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useGetClientIpQuery } from "@/controllers/API/queries/api-keys";

type FormKeyRenderModalProps = {
  inputLabel?: React.ReactNode;
  inputPlaceholder?: string;
};

export const FormKeyRender = ({
  modalProps,
  apiKeyName,
  inputRef,
  setApiKeyName,
  allowedIps,
  setAllowedIps,
}: {
  modalProps?: FormKeyRenderModalProps;
  apiKeyName: string;
  inputRef: React.RefObject<HTMLInputElement>;
  setApiKeyName: (value: string) => void;
  allowedIps?: string;
  setAllowedIps?: (value: string) => void;
}) => {
  const { data: clientIpData } = useGetClientIpQuery(undefined, {
    enabled: setAllowedIps !== undefined,
  });
  const clientIp = clientIpData?.ip ?? null;

  const handleUseMyIp = () => {
    if (!clientIp || !setAllowedIps) return;
    const current = allowedIps?.trim() ?? "";
    const entries = current ? current.split(";").map((s) => s.trim()) : [];
    if (!entries.includes(clientIp)) {
      setAllowedIps(entries.concat(clientIp).join(";"));
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Form.Field name="apikey">
        {modalProps?.inputLabel && (
          <Form.Label asChild className="mb-2">
            <Label className="relative bottom-1">
              {modalProps?.inputLabel as React.ReactNode}
            </Label>
          </Form.Label>
        )}

        <div className="flex items-center justify-between gap-2">
          <Form.Control asChild>
            <Input
              id="primary-input"
              value={apiKeyName}
              ref={inputRef}
              onChange={({ target: { value } }) => {
                setApiKeyName(value);
              }}
              placeholder={modalProps?.inputPlaceholder}
            />
          </Form.Control>
        </div>
      </Form.Field>

      {setAllowedIps !== undefined && (
        <Form.Field name="allowed_ips">
          <div className="mb-2 flex items-center justify-between">
            <Form.Label asChild>
              <Label>
                <span className="text-sm">IP Restriction</span>{" "}
                <span className="text-xs text-muted-foreground">
                  (optional)
                </span>
              </Label>
            </Form.Label>
            {clientIp && (
              <button
                type="button"
                onClick={handleUseMyIp}
                className="flex items-center gap-1 rounded-md border border-border bg-muted/50 px-2 py-0.5 font-mono text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                title="Add your current IP to the restriction list"
              >
                My IP: {clientIp}
              </button>
            )}
          </div>
          <Form.Control asChild>
            <Input
              value={allowedIps ?? ""}
              onChange={({ target: { value } }) => setAllowedIps(value)}
              placeholder="e.g. 1.2.3.4;10.0.%.%"
              className="font-mono text-sm"
            />
          </Form.Control>
          <p className="mt-1 text-xs text-muted-foreground">
            Semicolon-separated IPv4 patterns. Use{" "}
            <code className="rounded bg-muted px-0.5">%</code> as a wildcard for
            any octet. Leave empty to allow all IPs.
          </p>
        </Form.Field>
      )}
    </div>
  );
};
