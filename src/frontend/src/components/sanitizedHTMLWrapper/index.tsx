import DOMPurify from "dompurify";
import { forwardRef } from "react";
import { SanitizedHTMLWrapperType } from "../../types/components";

const SanitizedHTMLWrapper = forwardRef<
  HTMLDivElement,
  SanitizedHTMLWrapperType
>(({ className, content, suppressWarning = false, ...props }, ref) => {
  const sanitizedHTML = DOMPurify.sanitize(content);

  return (
    <div
      ref={ref}
      className={className}
      data-testid="edit-prompt-sanitized"
      dangerouslySetInnerHTML={{ __html: sanitizedHTML }}
      suppressContentEditableWarning={suppressWarning}
      {...props}
    />
  );
});

SanitizedHTMLWrapper.displayName = "SanitizedHTMLWrapper";

export default SanitizedHTMLWrapper;
