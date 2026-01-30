import "ace-builds/src-noconflict/ace";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-one_dark";
import AceEditor from "react-ace";
import { Copy, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog-with-no-close";
import BaseModal from "@/modals/baseModal";
import { useState } from "react";

const EDIT_CODE_SUBTITLE =
  "Edit your Python code snippet. Refer to the Langflow documentation for more information on how to write your own component.";

interface EditCodeModalProps {
  code: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (code: string) => void; // Nova prop para salvar
}

export function EditCodeModal({
  code,
  open,
  onOpenChange,
  onSave,
}: EditCodeModalProps) {
  const [editedCode, setEditedCode] = useState(code);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(editedCode);
  };

  const handleSave = () => {
    onSave(editedCode);
    onOpenChange(false);
  };

  return (
    <BaseModal open={open} setOpen={onOpenChange} size="x-large">
      <BaseModal.Trigger>{null}</BaseModal.Trigger>
      <BaseModal.Header description={EDIT_CODE_SUBTITLE}>
        <span className="pr-2">Edit Code</span>
      </BaseModal.Header>
      <BaseModal.Content overflowHidden>
        <div className="flex h-full w-full flex-col transition-all">
          <div className="relative h-full w-full">
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-2 top-2 z-10 h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={handleCopy}
            >
              <Copy className="h-4 w-4" />
            </Button>
            <AceEditor
              value={editedCode}
              onChange={setEditedCode}
              mode="python"
              theme="one_dark"
              setOptions={{ fontFamily: "monospace" }}
              height="100%"
              highlightActiveLine={false}
              showPrintMargin={false}
              fontSize={14}
              showGutter={false}
              name="EditCodeEditor"
              className="h-full min-w-full rounded-lg border-[1px] border-border custom-scroll"
            />
          </div>
          <div className="flex h-fit w-full justify-end">
            <Button className="mt-3" onClick={handleSave}>
              Check and Save
            </Button>
          </div>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}

const VIEW_CODE_SUBTITLE =
  "Review the generated Python code snippet. Refer to the Langflow documentation for more information on how to write your own component.";

interface ViewCodeModalProps {
  code: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ViewCodeModal({
  code,
  open,
  onOpenChange,
}: ViewCodeModalProps) {
  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex h-[535px] w-[770px] max-w-[770px] flex-col gap-0 overflow-hidden rounded-[10px] border border-border bg-background p-0 shadow-xl"
      >
        {/* Header */}
        <div className="flex flex-col gap-1 px-4 py-3 bg-muted">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">View Code</h2>
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="text-muted-foreground transition-colors hover:text-foreground text-xs"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <p className="text-sm text-muted-foreground">{VIEW_CODE_SUBTITLE}</p>
        </div>

        {/* Code Editor */}
        <div className="relative flex-1 overflow-hidden border border-border">
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-2 top-2 z-10 h-8 w-8 text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={handleCopy}
          >
            <Copy className="h-4 w-4" />
          </Button>
          <AceEditor
            readOnly
            value={code}
            mode="python"
            theme="one_dark"
            setOptions={{ fontFamily: "monospace" }}
            width="100%"
            height="100%"
            highlightActiveLine={false}
            showPrintMargin={false}
            fontSize={14}
            showGutter={false}
            name="ViewCodeEditor"
            style={{ backgroundColor: "#1E1E1E", fontSize: 12 }}
          />
        </div>

        {/* Footer */}
        <div className="flex justify-end px-6 py-4">
          <Button onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}