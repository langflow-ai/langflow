import { getBaseUrl } from "@/customization/utils/urls";

export const customBuildUrl = (flowId: string, playgroundPage?: boolean) => {
  return `${getBaseUrl()}${playgroundPage ? "build_public_tmp" : "build"}/${flowId}/flow`;
};

export const customCancelBuildUrl = (jobId: string) => {
  return `${getBaseUrl()}build/${jobId}/cancel`;
};

export const customEventsUrl = (jobId: string) => {
  return `${getBaseUrl()}build/${jobId}/events`;
};
