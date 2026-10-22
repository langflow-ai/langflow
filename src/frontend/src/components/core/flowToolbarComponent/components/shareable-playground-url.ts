/**
 * The public address of a flow's shareable playground.
 *
 * `basePath` is the app's router base (`useHref("/")`), which is `/` at the
 * root; concatenating it as is wrote `origin//playground/...`, and that address
 * opens the sign-in page instead of the playground.
 */
export const buildShareablePlaygroundUrl = (
  origin: string,
  basePath: string,
  flowId: string,
): string => {
  const base = basePath.endsWith("/") ? basePath : `${basePath}/`;
  return new URL(
    `playground/${encodeURIComponent(flowId)}`,
    `${origin}${base}`,
  ).toString();
};
