import { getBaseUrl } from "@/customization/utils/urls";

export const customBuildUrl = (flowId: string, playgroundPage?: boolean) => {
  return `${getBaseUrl()}${playgroundPage ? "build_public_tmp" : "build"}/${flowId}/flow`;
};

export const customCancelBuildUrl = (
  jobId: string,
  playgroundPage?: boolean,
) => {
  return `${getBaseUrl()}${playgroundPage ? "build_public_tmp" : "build"}/${jobId}/cancel`;
};

export const customEventsUrl = (
  jobId: string,
  playgroundPage?: boolean,
) => {
  return `${getBaseUrl()}${playgroundPage ? "build_public_tmp" : "build"}/${jobId}/events`;
};
