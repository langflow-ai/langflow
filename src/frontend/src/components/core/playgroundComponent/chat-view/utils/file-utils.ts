import { getBaseUrl } from "@/customization/utils/urls";

/**
 * Supported image file types
 */
const IMAGE_TYPES = new Set([
  "png",
  "jpg",
  "jpeg",
  "gif",
  "webp",
  "bmp",
  "image",
]);

/**
 * Check if a file is an image based on its type
 * @param file - Can be a File object, file type string, or file path string
 * @returns true if the file is an image
 */
export function isImageFile(
  file: File | { type: string } | { path: string; type: string } | string,
): boolean {
  if (file instanceof File) {
    // Browser File object
    const fileType = file.type.toLowerCase();
    return (
      fileType.startsWith("image/") ||
      IMAGE_TYPES.has(fileType.split("/").pop() || "")
    );
  } else if (typeof file === "string") {
    // File path string - extract extension
    const extension = file.split(".").pop()?.toLowerCase() || "";
    return IMAGE_TYPES.has(extension);
  } else if (file && typeof file === "object") {
    // Object with type or path property
    // For server files, check path extension first (most reliable)
    if ("path" in file && file.path) {
      const extension = file.path.split(".").pop()?.toLowerCase() || "";
      if (IMAGE_TYPES.has(extension)) {
        return true;
      }
    }
    // Also check type property as fallback
    if ("type" in file && file.type) {
      const fileType = file.type.toLowerCase();
      if (fileType.startsWith("image/") || IMAGE_TYPES.has(fileType)) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Get the display name for a file
 * @param file - Can be a File object, object with name property, or string path
 * @returns The file name
 */
export function getFileDisplayName(
  file: File | { name: string } | { path: string; name: string } | string,
): string {
  if (file instanceof File) {
    return file.name;
  } else if (typeof file === "string") {
    // Extract name from path
    return file.split("/").pop() || file;
  } else if ("name" in file) {
    return file.name;
  } else if ("path" in file) {
    return file.path.split("/").pop() || file.path;
  }
  return "";
}

/**
 * Format file name with truncation
 * @param name - File name to format
 * @param maxLength - Maximum length before truncation (default: 25)
 * @returns Formatted file name
 */
export function formatFileName(name: string, maxLength: number = 25): string {
  if (name[maxLength] === undefined) {
    return name;
  }
  const fileExtension = name.split(".").pop(); // Get the file extension
  const baseName = name.slice(0, name.lastIndexOf(".")); // Get the base name without the extension
  if (baseName.length > 6) {
    return `${baseName.slice(0, maxLength)}...${fileExtension}`;
  }
  return name;
}

/**
 * Get preview URL for a file (handles both File objects and server paths)
 * @param file - Can be a File object or server file path object
 * @returns Preview URL or null if not an image
 */
export function getFilePreviewUrl(
  file: File | { path: string; type: string } | string,
): string | null {
  if (!isImageFile(file)) {
    return null;
  }

  if (file instanceof File) {
    // Browser File object - create object URL
    return URL.createObjectURL(file);
  } else if (typeof file === "string") {
    // Server file path string - path format is "flow_id/filename"
    // Encode each path segment to handle spaces and special characters
    const path = file.trim();
    if (!path) return null;
    const encodedPath = path
      .split("/")
      .map((segment) => encodeURIComponent(segment))
      .join("/");
    // Explicitly use /api/v1/files/images/ prefix for server file paths
    return `${getBaseUrl()}files/images/${encodedPath}`;
  } else if ("path" in file) {
    // Server file path object - path format is "flow_id/filename"
    // Encode each path segment to handle spaces and special characters
    const path = file.path.trim();
    if (!path) return null;
    const encodedPath = path
      .split("/")
      .map((segment) => encodeURIComponent(segment))
      .join("/");
    // Explicitly use /api/v1/files/images/ prefix for server file paths
    return `${getBaseUrl()}files/images/${encodedPath}`;
  }

  return null;
}

/**
 * Extract file information from various file formats
 * @param file - Can be File, path string, or file object
 * @returns Object with name, type, and path
 */
export function extractFileInfo(
  file: File | { path: string; type: string; name: string } | string,
): { name: string; type: string; path: string } {
  if (file instanceof File) {
    return {
      name: file.name,
      type: file.type,
      path: file.name, // For File objects, path is just the name
    };
  } else if (typeof file === "string") {
    const name = file.split("/").pop() || file;
    const type = file.split(".").pop() || "";
    return { name, type, path: file };
  } else {
    return {
      name: file.name,
      type: file.type,
      path: file.path,
    };
  }
}
