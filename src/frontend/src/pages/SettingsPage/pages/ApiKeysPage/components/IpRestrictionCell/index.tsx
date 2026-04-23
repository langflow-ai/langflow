import type { ICellRendererParams } from "ag-grid-community";
import { isAxiosError } from "axios";
import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { usePatchApiKey } from "@/controllers/API/queries/api-keys";
import useAlertStore from "@/stores/alertStore";

export const IpRestrictionCell = (params: ICellRendererParams) => {
  const value: string | null = params.value ?? null;
  const rowId: string = params.data?.id ?? "";
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value ?? "");
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { mutate } = usePatchApiKey();

  const handleOpen = (isOpen: boolean) => {
    if (isOpen) {
      setInputValue(value ?? "");
    }
    setOpen(isOpen);
  };

  const handleSave = () => {
    mutate(
      { keyId: rowId, allowed_ips: inputValue.trim() || null },
      {
        onSuccess: () => {
          setOpen(false);
          setSuccessData({ title: "IP restriction updated" });
          params.api.refreshCells({ rowNodes: [params.node], force: true });
          if (params.node.data) {
            params.node.setDataValue("allowed_ips", inputValue.trim() || null);
          }
        },
        onError: (error: unknown) => {
          let detail = "Unknown error";
          if (isAxiosError(error) && error.response?.data) {
            const data = error.response.data;
            if (typeof data === "object" && data !== null && "detail" in data) {
              const d = (data as { detail: unknown }).detail;
              detail = Array.isArray(d)
                ? d.map(String).join(", ")
                : typeof d === "string"
                  ? d
                  : String(d);
            }
          }
          setErrorData({
            title: "Failed to update IP restriction",
            list: [detail],
          });
        },
      },
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") setOpen(false);
  };

  return (
    <div className="flex h-full w-full items-center gap-1">
      <span className="truncate text-sm text-muted-foreground">
        {value || <span className="italic opacity-50">—</span>}
      </span>
      <Popover open={open} onOpenChange={handleOpen}>
        <PopoverTrigger asChild>
          <button
            className="ml-1 flex-shrink-0 rounded p-0.5 opacity-0 transition-opacity hover:bg-accent group-hover:opacity-100 focus:opacity-100"
            aria-label="Edit IP restriction"
            onClick={(e) => e.stopPropagation()}
          >
            <ForwardedIconComponent
              name="Pencil"
              className="h-3 w-3 text-muted-foreground"
            />
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-96 p-3" side="bottom" align="start">
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">IP Restriction</p>
            <p className="text-xs text-muted-foreground">
              Semicolon-separated IPv4 patterns. Use{" "}
              <code className="rounded bg-muted px-0.5">%</code> as a wildcard
              for any octet (0–255).
              <br />
              Example:{" "}
              <code className="rounded bg-muted px-0.5">1.2.3.4;10.0.%.%</code>
            </p>
            <Input
              autoFocus
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Leave empty to allow all IPs"
              className="h-8 text-sm"
            />
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button variant="primary" size="sm" onClick={handleSave}>
                Save
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
};
