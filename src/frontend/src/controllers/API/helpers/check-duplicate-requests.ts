import { AUTHORIZED_DUPLICATE_REQUESTS } from "../../../constants/constants";

export function checkDuplicateRequestAndStoreRequest(config) {
  const lastUrl = localStorage.getItem("lastUrlCalled");
  const lastMethodCalled = localStorage.getItem("lastMethodCalled");
  const lastRequestTime = localStorage.getItem("lastRequestTime");
  const lastCurrentUrl = localStorage.getItem("lastCurrentUrl");

  const currentUrl = window.location.pathname;
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
    currentTime - parseInt(lastRequestTime, 10) < 300 &&
    lastCurrentUrl === currentUrl
  ) {
    throw new Error("Duplicate request: " + lastUrl);
  }

  localStorage.setItem("lastUrlCalled", config.url ?? "");
  localStorage.setItem("lastMethodCalled", config.method ?? "");
  localStorage.setItem("lastRequestTime", currentTime.toString());
  localStorage.setItem("lastCurrentUrl", currentUrl);
}
