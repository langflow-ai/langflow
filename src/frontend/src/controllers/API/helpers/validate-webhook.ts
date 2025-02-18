export const validateWebhookData = (res) => {
  if (!res?.data?.vertex_builds) {
    return false;
  }
  return Object.keys(res?.data?.vertex_builds).some(
    (key) =>
      key.includes("Webhook") &&
      Array.isArray(res?.data?.vertex_builds[key]) &&
      res?.data?.vertex_builds[key]?.length > 0,
  );
};
