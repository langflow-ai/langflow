import * as React from "react";
import { cn } from "../../utils/utils";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  password?: boolean;
  editNode?: boolean;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, password, editNode, ...props }, ref) => {
    return (
      <div className="h-full w-full">
        <textarea
          data-testid="textarea"
          className={cn(
            "nopan nodelete nodrag noflow nowheel border hover:border-secondary-border focus:border-secondary-border w-full py-2 px-3 bg-background-surface rounded-md border-primary-border min-h-[38px] text-primary-font text-sm placeholder:opacity-70",
            className,
            password ? "password" : ""
          )}
          ref={ref}
          {...props}
          value={props.value as string}
          onChange={props.onChange}
        />
      </div>
    );
  }
);

Textarea.displayName = "Textarea";

export { Textarea };
