type Environment = "dev" | "test" | "feature" | "prod" | "unknown";

// Keep this for LF, will be different for DSLF
const useDetermineEnv = (): Environment => {
  const hostname = window.location.hostname;

  if (hostname === "localhost") {
    return "dev";
  }
  return "unknown";
};

export default useDetermineEnv;
