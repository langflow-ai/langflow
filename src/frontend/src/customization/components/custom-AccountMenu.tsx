import {
  DropdownMenu,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CustomProfileIcon } from "./custom-profile-icon";
import {
  HeaderMenuItems,
  HeaderMenuItemButton,
} from "@/components/core/appHeaderComponent/components/HeaderMenu";
import { useLogout } from "@/controllers/API/queries/auth";
import { envConfig } from "@/config/env";
import KeycloakService from "@/services/keycloak";
import { BASENAME } from "@/customization/config-constants";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useNavigate } from "react-router-dom";

export function CustomAccountMenu() {
  const { mutate: mutationLogout } = useLogout();
  const navigate = useNavigate();

  const handleLogout = async () => {
    if (envConfig.keycloakEnabled) {
      try {
        useAuthStore.getState().logout();
        useFlowStore.getState().resetFlowState();
        useFlowsManagerStore.getState().resetStore();
        useFolderStore.getState().resetStore();
        const redirectToLogin = `${window.location.origin}${
          BASENAME || ""
        }/login`;
        await KeycloakService.getInstance().logout(redirectToLogin);
      } catch (error) {
        console.error(
          "Keycloak logout failed, falling back to API logout:",
          error
        );
        mutationLogout();
      }
      return;
    }

    mutationLogout();
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="inline-flex items-center justify-center rounded-md focus-visible:outline-none"
        data-testid="user_menu_button"
        id="user_menu_button"
      >
        <div className="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-white/30 hover:bg-white/40 transition-colors">
          <div className="h-6 w-6">
            <CustomProfileIcon />
          </div>
        </div>
      </DropdownMenuTrigger>
      <HeaderMenuItems position="right" classNameSize="w-[180px]">
        <div className="py-1 bg-background-surface">
          <HeaderMenuItemButton
            onClick={() => navigate("/settings/general")}
            icon="settings"
          >
            Settings
          </HeaderMenuItemButton>
          <HeaderMenuItemButton onClick={handleLogout} icon="log-out">
            Logout
          </HeaderMenuItemButton>
        </div>
      </HeaderMenuItems>
    </DropdownMenu>
  );
}

export default CustomAccountMenu;
