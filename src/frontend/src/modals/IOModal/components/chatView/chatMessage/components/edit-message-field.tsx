import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

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
  // used before to onBlur function, leave it here because in the future we may want this functionality again
  const [_isButtonClicked, setIsButtonClicked] = useState(false);
  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${
        textareaRef.current.scrollHeight + 3
      }px`;
    }
  };
  useEffect(() => {
    adjustTextareaHeight();
  }, []);

  return (
    <div className="flex h-fit w-full flex-col rounded-md bg-background-mainBg px-4 py-2">
      <Textarea
        ref={textareaRef}
        className="max-h-[400px] w-full resize-none rounded-none border-0 bg-background-mainBg shadow-none focus:ring-0"
        // onBlur={() => {
        //   if (!isButtonClicked) {
        //     onCancel();
        //   }
        // }}
        value={message}
        autoFocus={true}
        onChange={(e) => setMessage(e.target.value)}
      />
      <div className="flex w-full flex-row-reverse justify-between">
        <div className="flex w-full flex-row-reverse items-center justify-between">
          <div className="flex min-w-fit flex-row-reverse gap-2">
            <Button
              variant="default"
              data-testid="save-button"
              onMouseDown={() => setIsButtonClicked(true)}
              onClick={() => {
                onEdit(message);
                setIsButtonClicked(false);
              }}
              className="mt-2"
            >
              Save
            </Button>
            <Button
              variant="outline"
              data-testid="cancel-button"
              onMouseDown={() => setIsButtonClicked(true)}
              onClick={() => {
                onCancel();
                setIsButtonClicked(false);
              }}
              className="mt-2"
            >
              Cancel
            </Button>
          </div>
          <div className="text-mmd font-medium text-secondary-font word-break-break-word">
            Editing messages will update the memory but won't restart the
            conversation.
          </div>
        </div>
        <div></div>
      </div>
    </div>
  );
}
