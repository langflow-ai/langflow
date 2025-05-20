import { BASE_URL_API } from "@/constants/constants";

export const customBuildUrl = (flowId: string, playgroundPage?: boolean) => {
  return `${BASE_URL_API}${playgroundPage ? "build_public_tmp" : "build"}/${flowId}/flow`;
};

export const customCancelBuildUrl = (jobId: string) => {
  return `${BASE_URL_API}build/${jobId}/cancel`;
};

export const customEventsUrl = (jobId: string) => {
  return `${BASE_URL_API}build/${jobId}/events`;
};
