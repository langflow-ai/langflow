import { useAuth } from "@clerk/clerk-react";

// Returns a function to get the Clerk session token (or null if not signed in)
export function useClerkAccessToken() {
  const { getToken } = useAuth();
  return async () => {
    try {
      return await getToken();
    } catch {
      return null;
    }
  };
}
