export const ACCESS_TOKEN_EXPIRE_SECONDS_ENV_KEY =
  "__LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS__";
export const DEFAULT_ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60;

export const createAccessTokenExpireSecondsDefinition = (
  configuredValue?: string,
) => ({
  [ACCESS_TOKEN_EXPIRE_SECONDS_ENV_KEY]: JSON.stringify(
    configuredValue ?? DEFAULT_ACCESS_TOKEN_EXPIRE_SECONDS,
  ),
});
