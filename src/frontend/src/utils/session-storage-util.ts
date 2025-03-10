export const getSessionStorage = (key: string) => {
  return sessionStorage.getItem(key);
};

export const setSessionStorage = (key: string, value: string) => {
  sessionStorage.setItem(key, value);
};

export const removeSessionStorage = (key: string) => {
  sessionStorage.removeItem(key);
};
