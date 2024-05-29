import DOMPurify from "dompurify";
import { SanitizedHTMLWrapperType } from "../../types/components";

const SanitizedHTMLWrapper = ({
  className,
  content,
  onClick,
  suppressWarning = false,
}: SanitizedHTMLWrapperType): JSX.Element => {
  const sanitizedHTML = DOMPurify.sanitize(content);

  return (
    <div
      data-testid="edit-prompt-sanitized"
      className={className}
      dangerouslySetInnerHTML={{ __html: sanitizedHTML }}
      suppressContentEditableWarning={suppressWarning}
      onClick={onClick}
    />
  );
};

export default SanitizedHTMLWrapper;
