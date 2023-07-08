import DOMPurify from "dompurify";

const SanitizedHTMLWrapper = ({
  className,
  content,
  onClick,
  suppressWarning = false,
}) => {
  const sanitizedHTML = DOMPurify.sanitize(content);

  return (
    <div
      className={className}
      dangerouslySetInnerHTML={{ __html: sanitizedHTML }}
      suppressContentEditableWarning={suppressWarning}
      onClick={onClick}
    />
  );
};

export default SanitizedHTMLWrapper;
