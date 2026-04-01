/**
 * Helper function to format numbers with commas
 */
export const formatNumber = (num: number): string => {
  return new Intl.NumberFormat().format(num);
};

/**
 * Format average chunk size with units
 */
export const formatAverageChunkSize = (avgChunkSize: number): string => {
  return `${formatNumber(Math.round(avgChunkSize))}`;
};
