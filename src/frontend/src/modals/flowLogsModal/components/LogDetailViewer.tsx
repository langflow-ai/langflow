import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface LogDetailViewerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  content: Record<string, unknown> | null;
}

export function LogDetailViewer({
  open,
  onOpenChange,
  title,
  content,
}: LogDetailViewerProps): JSX.Element {
  const formatContent = (data: Record<string, unknown> | null): string => {
    if (data === null || data === undefined) {
      return "No data available";
    }
    try {
      return JSON.stringify(data, null, 2);
    } catch {
      return String(data);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] max-w-2xl overflow-hidden">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="max-h-[60vh] overflow-auto">
          <SimplifiedCodeTabComponent
            language="json"
            code={formatContent(content)}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
