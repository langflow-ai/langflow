import {
  ALLOWED_CHAT_ATTACHMENT_INPUT_EXTENSIONS,
  ALLOWED_CHAT_ATTACHMENT_INPUT_MIME_TYPES,
  ALLOWED_IMAGE_INPUT_EXTENSIONS,
  ALLOWED_IMAGE_INPUT_MIME_TYPES,
} from "@/constants/constants";

export const getFileExtension = (fileName: string): string => {
  const fileParts = fileName.split(".");
  if (fileParts.length <= 1) {
    return "";
  }

  const lastPart = fileParts[fileParts.length - 1]?.toLowerCase() ?? "";
  return lastPart.length > 0 ? lastPart : "";
};

export const hasFileExtension = (fileName: string): boolean => {
  const fileParts = fileName.split(".");
  return fileParts.length > 1 && fileParts[fileParts.length - 1].length > 0;
};

export const isAllowedChatAttachmentFile = (file: File): boolean => {
  const fileType = file.type.toLowerCase();
  const fileExtension = getFileExtension(file.name);
  const hasNamedExtension = hasFileExtension(file.name);
  const hasAllowedExtension =
    ALLOWED_CHAT_ATTACHMENT_INPUT_EXTENSIONS.includes(fileExtension);
  const hasAllowedMime =
    ALLOWED_CHAT_ATTACHMENT_INPUT_MIME_TYPES.includes(fileType);
  const extensionIsImage =
    ALLOWED_IMAGE_INPUT_EXTENSIONS.includes(fileExtension);
  const mimeIsImage = ALLOWED_IMAGE_INPUT_MIME_TYPES.includes(fileType);

  if (hasNamedExtension && !hasAllowedExtension) {
    return false;
  }

  if (
    hasNamedExtension &&
    fileType.length > 0 &&
    extensionIsImage !== mimeIsImage
  ) {
    return false;
  }

  if (fileType.length > 0) {
    return hasAllowedMime;
  }

  return hasAllowedExtension;
};
