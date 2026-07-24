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
    delete process.env.ACCESS_TOKEN_EXPIRE_SECONDS;
    jest.resetModules();

    const { LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV } = await import(
      "../constants"
    );

    expect(LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV).toBe(3240);
  });

  it("refreshes 10% before a configured expiry", async () => {
    process.env.ACCESS_TOKEN_EXPIRE_SECONDS = "7200";
    jest.resetModules();

    const { LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV } = await import(
      "../constants"
    );

    expect(LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV).toBe(6480);
  });
});
