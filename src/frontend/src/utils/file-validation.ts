import {
  CHAT_UPLOAD_ATTACHMENT_EXTENSIONS,
  CHAT_UPLOAD_ATTACHMENT_MIME_TYPES,
  CHAT_UPLOAD_IMAGE_EXTENSIONS,
  CHAT_UPLOAD_IMAGE_MIME_TYPES,
} from "@/constants/file-upload-constants";

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
    CHAT_UPLOAD_ATTACHMENT_EXTENSIONS.includes(fileExtension);
  const hasAllowedMime = CHAT_UPLOAD_ATTACHMENT_MIME_TYPES.includes(fileType);
  const extensionIsImage = CHAT_UPLOAD_IMAGE_EXTENSIONS.includes(fileExtension);
  const mimeIsImage = CHAT_UPLOAD_IMAGE_MIME_TYPES.includes(fileType);

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
