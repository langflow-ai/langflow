export const CHAT_UPLOAD_IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "bmp"];

export const CHAT_UPLOAD_IMAGE_MIME_TYPES = [
  "image/png",
  "image/jpeg",
  "image/bmp",
];

export const CHAT_UPLOAD_IMAGE_ACCEPT =
  ".png,.jpg,.jpeg,.bmp,image/png,image/jpeg,image/bmp";

export const CHAT_UPLOAD_IMAGE_TOOLTIP = "Attach image (png, jpg, jpeg, bmp)";

export const CHAT_UPLOAD_ATTACHMENT_EXTENSIONS = [
  "csv",
  "docx",
  "json",
  "pdf",
  "txt",
  "md",
  "mdx",
  "yaml",
  "yml",
  "xml",
  "html",
  "htm",
  "tsx",
  "py",
  "sh",
  "sql",
  "js",
  "ts",
  "jpg",
  "jpeg",
  "png",
  "bmp",
];

export const CHAT_UPLOAD_ATTACHMENT_MIME_TYPES = [
  "application/pdf",
  "text/csv",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "text/markdown",
  "text/mdx",
  "application/mdx",
  "application/json",
  "application/x-yaml",
  "application/yaml",
  "text/yaml",
  "application/xml",
  "text/xml",
  "text/html",
  "text/javascript",
  "application/javascript",
  "text/typescript",
  "text/x-typescript",
  "text/x-tsx",
  "application/sql",
  "text/x-sql",
  "application/x-sh",
  "text/x-python",
  "image/png",
  "image/jpeg",
  "image/bmp",
];

export const CHAT_UPLOAD_ATTACHMENT_ACCEPT =
  ".csv,.json,.pdf,.txt,.md,.mdx,.yaml,.yml,.xml,.html,.htm,.docx,.py,.sh,.sql,.js,.ts,.tsx,.jpg,.jpeg,.png,.bmp,application/pdf,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown,application/json,application/x-yaml,application/yaml,text/yaml,application/xml,text/xml,text/html,text/javascript,application/javascript,text/typescript,text/x-typescript,text/x-tsx,application/sql,text/x-sql,application/x-sh,text/x-python,image/png,image/jpeg,image/bmp";

export const CHAT_UPLOAD_ATTACHMENT_TOOLTIP =
  "Attach file (images, pdf, csv, docx, txt, md, json, yaml, xml, html, code files)";

export const FS_ERROR_TEXT =
  "Unsupported attachment type. Supported chat attachments include images, PDF, CSV, DOCX, and common text/code files.";

export const SN_ERROR_TEXT = CHAT_UPLOAD_ATTACHMENT_EXTENSIONS.join(", ");
