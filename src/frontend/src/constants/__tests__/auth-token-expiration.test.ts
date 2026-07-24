import {
  ACCESS_TOKEN_EXPIRE_SECONDS_ENV_KEY,
  createAccessTokenExpireSecondsDefinition,
} from "../../../vite-env-definitions";

describe("authentication token refresh timing", () => {
  const originalAccessTokenExpiry = process.env.ACCESS_TOKEN_EXPIRE_SECONDS;

  afterEach(() => {
    if (originalAccessTokenExpiry === undefined) {
      delete process.env.ACCESS_TOKEN_EXPIRE_SECONDS;
    } else {
      process.env.ACCESS_TOKEN_EXPIRE_SECONDS = originalAccessTokenExpiry;
    }
    jest.resetModules();
  });

  it("defaults to refreshing 10% before the one-hour backend expiry", async () => {
    const definitions = createAccessTokenExpireSecondsDefinition();
    expect(definitions[ACCESS_TOKEN_EXPIRE_SECONDS_ENV_KEY]).toBe("3600");
    process.env.ACCESS_TOKEN_EXPIRE_SECONDS = String(
      JSON.parse(definitions[ACCESS_TOKEN_EXPIRE_SECONDS_ENV_KEY]),
    );
    jest.resetModules();

    const { LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV } = await import(
      "../constants"
    );

    expect(LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV).toBe(3240);
  });

  it("refreshes 10% before a configured expiry", async () => {
    const definitions = createAccessTokenExpireSecondsDefinition("7200");
    expect(definitions[ACCESS_TOKEN_EXPIRE_SECONDS_ENV_KEY]).toBe('"7200"');
    process.env.ACCESS_TOKEN_EXPIRE_SECONDS = String(
      JSON.parse(definitions[ACCESS_TOKEN_EXPIRE_SECONDS_ENV_KEY]),
    );
    jest.resetModules();

    const { LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV } = await import(
      "../constants"
    );

    expect(LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV).toBe(6480);
  });
});
