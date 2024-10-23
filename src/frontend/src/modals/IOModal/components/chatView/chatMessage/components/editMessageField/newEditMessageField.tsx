import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useEffect, useRef, useState } from "react";

export default function EditMessageField({
  message: initialMessage,
  onEdit,
  onCancel,
}: {
  message: string;
  onEdit: (message: string) => void;
  onCancel: () => void;
}) {
  const [message, setMessage] = useState(initialMessage);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isButtonClicked, setIsButtonClicked] = useState(false);
  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight + 3}px`;
    }
  };
  useEffect(() => {
    adjustTextareaHeight();
  }, []);

  return (
    <div className="flex h-fit w-full flex-col bg-muted dark:bg-zinc-800">
      <Textarea
        ref={textareaRef}
        className="h-mx-full w-full resize-none border-0 rounded-none shadow-none bg-muted dark:bg-zinc-800 focus:ring-0"
        onBlur={() => {
          if (!isButtonClicked) {
            onCancel();
          }
        }}
        value={message}
        autoFocus={true}
        onChange={(e) => setMessage(e.target.value)}
      />
      <div className="flex w-full flex-row-reverse justify-between">
        <div className="flex flex-row-reverse gap-2">
          <Button
            data-testid="save-button"
            variant={"primary"}
            onMouseDown={() => setIsButtonClicked(true)}
            onClick={() => {
              onEdit(message);
              setIsButtonClicked(false);
            }}
            className="mt-2 bg-black text-white hover:bg-white hover:text-black dark:text-white dark:hover:!bg-zinc-950"
          >
            Save
          </Button>
          <Button
            variant={"secondary"}
            data-testid="cancel-button"
            onMouseDown={() => setIsButtonClicked(true)}
            onClick={() => {
              onCancel();
              setIsButtonClicked(false);
            }}
            className="mt-2 bg-[#e4e4e7] dark:bg-white !text-black hover:bg-white"
          >
            Cancel
          </Button>
        </div>
        <div>
          <span className="mr-4 text-sm text-muted-foreground">
            Editing messages will update the memory but won't restart the
            conversation.
          </span>
        </div>
      </div>
    </div>
  );
}
