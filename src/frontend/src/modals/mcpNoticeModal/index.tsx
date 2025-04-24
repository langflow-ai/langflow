import MCPLangflow from "@/assets/MCPLangflow.png";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import BaseModal from "../baseModal";

export default function MCPNoticeModal({
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
}): JSX.Element {
  const navigate = useCustomNavigate();
  return (
    <BaseModal
      size="notice"
      open={open}
      setOpen={setOpen}
      closeButtonClassName="hidden"
    >
      <BaseModal.Content>
        <div className="flex flex-col gap-4">
          <img src={MCPLangflow} alt="MCP Notice Modal" />
          <div className="text-lg">Introducing Projects as MCP Servers</div>

          <p className="text-sm">
            One-click setup to expose flows as callable actions from external
            clients like Cursor or Claude.
          </p>
          <p className="text-sm">
            Explore this{" "}
            <a
              href="https://docs.langflow.org/mcp-projecrts"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-pink-foreground"
            >
              example project
            </a>{" "}
            for a downloadable project you can use as a MCP Server.
          </p>
        </div>
        <BaseModal.Footer>
          <div className="mt-6 flex gap-3">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Close
            </Button>
            <Button
              onClick={() => {
                navigate("/mcp");
                setOpen(false);
              }}
            >
              Go to Server
            </Button>
          </div>
        </BaseModal.Footer>
      </BaseModal.Content>
    </BaseModal>
  );
}
