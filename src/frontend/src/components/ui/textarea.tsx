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
            "nopan nodelete nodrag noflow textarea-primary nowheel",
            className,
            password ? "password" : "",
          )}
          ref={ref}
          {...props}
          value={props.value as string}
          onChange={props.onChange}
        />
      </div>
    );
  },
);

Textarea.displayName = "Textarea";

export { Textarea };
