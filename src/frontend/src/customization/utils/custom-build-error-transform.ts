/**
 * Transforms build error messages before displaying to the user.
 * Override this in desktop/custom builds to replace OSS-specific
 * messages with platform-appropriate instructions.
 */
export function transformBuildErrorMessages(messages: string[]): string[] {
  return messages;
}
