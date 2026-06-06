/**
 * 安全地从 localStorage 读取字符串值。
 * Safely reads a string value from localStorage.
 *
 * @param key - 要读取的存储键。 / Storage key to read.
 * @returns 存储的值；存储不可用时返回 null。 / The stored value, or null when storage is unavailable.
 */
export const getLocalStorage = (key: string): string | null => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};

/**
 * 安全地向 localStorage 写入字符串值。
 * Safely writes a string value to localStorage.
 *
 * @param key - 要写入的存储键。 / Storage key to write.
 * @param value - 要写入的存储值。 / Storage value to write.
 * @returns 无返回值。 / Nothing.
 */
export const setLocalStorage = (key: string, value: string): void => {
  try {
    localStorage.setItem(key, value);
  } catch {}
};

/**
 * 安全地从 localStorage 移除值。
 * Safely removes a value from localStorage.
 *
 * @param key - 要移除的存储键。 / Storage key to remove.
 * @returns 无返回值。 / Nothing.
 */
export const removeLocalStorage = (key: string): void => {
  try {
    localStorage.removeItem(key);
  } catch {}
};
