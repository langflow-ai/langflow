import {
  DropdownMenu,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CustomProfileIcon } from "./custom-profile-icon";
import { HeaderMenuItems, HeaderMenuItemButton } from "@/components/core/appHeaderComponent/components/HeaderMenu";

export function CustomAccountMenu() {
  const handleLogout = () => {
    // TODO: Implement real logout logic later
    console.log("Logout clicked");
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="inline-flex items-center justify-center rounded-md focus-visible:outline-none"
        data-testid="user_menu_button"
        id="user_menu_button"
      >
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 hover:bg-white/20 transition-colors">
          <div className="h-6 w-6">
            <CustomProfileIcon />
          </div>
        </div>
      </DropdownMenuTrigger>
      <HeaderMenuItems position="right" classNameSize="w-[200px]">
        <div className="py-1">
          <HeaderMenuItemButton onClick={handleLogout} icon="log-out">
            Logout
          </HeaderMenuItemButton>
        </div>
      </HeaderMenuItems>
    </DropdownMenu>
  );
}

export default CustomAccountMenu;
