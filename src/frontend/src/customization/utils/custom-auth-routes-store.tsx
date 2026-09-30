// OSS no-op; downstream overlays register additional pre-auth routes here
// (e.g. an SSO enterprise layer's `/login/break-glass`). Mounted as a sibling
// of `login` / `signup` / `login/admin` in routes.tsx — outside the
// authenticated route tree, so it's reachable before sign-in.
export const CustomAuthRoutesStore = () => {
  return null;
};

export default CustomAuthRoutesStore;
