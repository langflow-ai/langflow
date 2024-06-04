import { AUTHORIZED_DUPLICATE_REQUESTS } from "../../../constants/constants";

export function checkDuplicateRequestAndStoreRequest(config) {
  const lastUrl = localStorage.getItem("lastUrlCalled");
  const lastMethodCalled = localStorage.getItem("lastMethodCalled");
  const lastRequestTime = localStorage.getItem("lastRequestTime");

  const currentTime = Date.now();

  const isContained = AUTHORIZED_DUPLICATE_REQUESTS.some((request) =>
    config?.url!.includes(request),
  );

  if (
    config?.url === lastUrl &&
    !isContained &&
    lastMethodCalled === config.method &&
    lastMethodCalled === "get" && // Assuming you want to check only for GET requests
    lastRequestTime &&
    currentTime - parseInt(lastRequestTime, 10) < 800
  ) {
    return false;
  }

  localStorage.setItem("lastUrlCalled", config.url ?? "");
  localStorage.setItem("lastMethodCalled", config.method ?? "");
  localStorage.setItem("lastRequestTime", currentTime.toString());

  return true;
}
