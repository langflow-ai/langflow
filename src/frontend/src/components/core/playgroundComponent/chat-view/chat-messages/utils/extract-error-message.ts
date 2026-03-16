/**
 * Extracts the error message from a reason string that may contain JSON-like structures.
 *
 * @param reason - The error reason string that may contain JSON with error details
 * @returns The extracted error message, or null if extraction fails
 *
 * @example
 * const reason = "**BadRequestError**\n - **Details: Error code: 400 - {'type': 'error', 'error': {'message': 'Your credit balance is too low...'}}**\n";
 * const message = extractErrorMessage(reason);
 * // Returns: "Your credit balance is too low..."
 */
export function extractErrorMessage(reason: string | undefined): string | null {
  if (!reason) return null;

  try {
    // Try to find JSON-like structure in the reason string
    // Look for patterns like {'type': 'error', 'error': {'message': '...'}}
    const jsonMatch = reason.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      // Replace single quotes with double quotes for JSON parsing
      const jsonStr = jsonMatch[0].replace(/'/g, '"');
      const parsed = JSON.parse(jsonStr);

      // Try to get message from error.error.message
      if (parsed?.error?.message) {
        return parsed.error.message;
      }
      // Fallback to error.message
      if (parsed?.message) {
        return parsed.message;
      }
    }
  } catch (e) {
    // If parsing fails, return null to fall back to showing the full reason
  }

  return null;
}
