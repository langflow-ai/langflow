import React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Copy, Check } from "lucide-react";

interface SampleTextModalProps {
  isOpen: boolean;
  onClose: () => void;
  text: string;
  index: number;
  title?: string;
}

export const SampleTextModal: React.FC<SampleTextModalProps> = ({
  isOpen,
  onClose,
  text,
  index,
  title,
}) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text:", err);
    }
  };

  // Check if text is JSON and format it
  const isJsonString = (str: string): boolean => {
    if (!str || typeof str !== 'string') return false;
    const trimmed = str.trim();
    if (!trimmed) return false;
    
    if (
      (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
      (trimmed.startsWith('[') && trimmed.endsWith(']'))
    ) {
      try {
        JSON.parse(trimmed);
        return true;
      } catch {
        return false;
      }
    }
    return false;
  };

  const formatJson = (jsonString: string): string => {
    try {
      const parsed = JSON.parse(jsonString);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return jsonString;
    }
  };

  const displayText = isJsonString(text) ? formatJson(text) : text;
  const isJson = isJsonString(text);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-lg font-semibold">
              {title ?? `Sample Input Text ${index + 1}`}
            </DialogTitle>
            <Button
              onClick={handleCopy}
              size="sm"
              variant="outline"
              className="gap-2"
            >
              {copied ? (
                <>
                  <Check className="h-4 w-4" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4" />
                  Copy
                </>
              )}
            </Button>
          </div>
          {isJson && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground pt-1">
              <span className="px-2 py-1 bg-muted rounded text-xs font-medium uppercase">
                JSON
              </span>
            </div>
          )}
        </DialogHeader>

        <div className="flex-1 overflow-auto mt-4">
          {isJson ? (
            <pre className="bg-gray-50 dark:bg-gray-900 p-4 rounded-md text-xs font-mono border border-gray-200 dark:border-gray-700 overflow-x-auto">
              <code className="text-gray-800 dark:text-gray-200">{displayText}</code>
            </pre>
          ) : (
            <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-md border border-gray-200 dark:border-gray-700 overflow-auto">
              <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words">
                {displayText}
              </p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};