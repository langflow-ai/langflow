import { useLogout } from "@/controllers/API/queries/auth/use-logout";
import useAuthStore from "@/stores/authStore";
import { useNavigate } from "react-router-dom";

export function useLogoutHook() {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);
  const { mutate } = useLogout({
    onSuccess: () => {
      logout();
      navigate("/login");
    },
    onError: (error) => {
      console.error(error);
    },
  });

  return { logout: () => mutate({}) };
}
