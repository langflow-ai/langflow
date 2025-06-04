import { useState } from "react";

import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import { Textarea } from "@/components/ui/textarea";
import { useAddMCPServer } from "@/controllers/API/queries/mcp/use-add-mcp-server";
import { CustomLink } from "@/customization/components/custom-link";
import BaseModal from "@/modals/baseModal";
import { MCPServerType } from "@/types/mcp";
import { extractMcpServersFromJson } from "@/utils/mcpUtils";

//TODO IMPLEMENT FORM LOGIC

export default function AddMcpServerModal({
  children,
  initialData,
  open: myOpen,
  setOpen: mySetOpen,
}: {
  children?: JSX.Element;
  initialData?: MCPServerType;
  open?: boolean;
  setOpen?: (a: boolean | ((o?: boolean) => boolean)) => void;
}): JSX.Element {
  const [open, setOpen] =
    mySetOpen !== undefined && myOpen !== undefined
      ? [myOpen, mySetOpen]
      : useState(false);

  const [type, setType] = useState("JSON");
  const [jsonValue, setJsonValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { mutateAsync: addMCPServer, isPending } = useAddMCPServer();

  async function submitForm() {
    setError(null);
    let servers: MCPServerType[];
    try {
      servers = extractMcpServersFromJson(jsonValue);
    } catch (e: any) {
      setError(e.message || "Invalid input");
      return;
    }
    if (servers.length === 0) {
      setError("No valid MCP server found in the input.");
      return;
    }
    try {
      await Promise.all(servers.map((server) => addMCPServer(server)));
      setOpen(false);
      setJsonValue("");
      setError(null);
    } catch (err: any) {
      setError(err?.message || "Failed to add one or more MCP servers.");
    }
  }

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="x-small"
      onSubmit={submitForm}
      className="!p-4"
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Content className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 tracking-normal">
          <div className="flex items-center gap-2 text-sm font-medium">
            <ForwardedIconComponent
              name="Mcp"
              className="h-4 w-4 text-primary"
              aria-hidden="true"
            />
            {initialData ? "Update MCP Server" : "Add MCP Server"}
          </div>
          <span className="text-mmd font-normal text-muted-foreground">
            Save MCP Servers. Manage added connections in{" "}
            <CustomLink className="underline" to="/settings/mcp-servers">
              settings
            </CustomLink>
            .
          </span>
        </div>
        <div className="flex h-full w-full flex-col gap-4">
          <div className="">
            <Tabs
              defaultValue={type}
              onValueChange={setType}
              className="w-full"
            >
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger data-testid="json-tab" value="JSON">
                  JSON
                </TabsTrigger>
                <TabsTrigger data-testid="stdio-tab" value="STDIO">
                  STDIO
                </TabsTrigger>
                <TabsTrigger data-testid="json-tab" value="SSE">
                  SSE
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          <div className="space-y-2" id="global-variable-modal-inputs">
            <Label className="!text-mmd">Paste in JSON config</Label>
            {error && (
              <div className="mb-2 text-sm font-medium text-red-500">
                {error}
              </div>
            )}
            <Textarea
              value={jsonValue}
              onChange={(e) => setJsonValue(e.target.value)}
              className="min-h-40 font-mono text-mmd"
              placeholder="Paste in JSON config to add server"
              disabled={isPending}
            />
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
            <span className="text-mmd font-normal">Cancel</span>
          </Button>
          <Button size="sm" onClick={submitForm} loading={isPending}>
            <span className="text-mmd">
              {initialData ? "Update Server" : "Add Server"}
            </span>
          </Button>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
