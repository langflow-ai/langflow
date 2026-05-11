import { useContext } from "react";
import { AuthContext } from "@/contexts/authContext";
import { BASE_URL_API } from "@/customization/config-constants";

interface ProfileIconProps {
  className?: string;
}

export function ProfileIcon({ className }: ProfileIconProps = {}) {
  const { userData } = useContext(AuthContext);

  const profileImageUrl = `${BASE_URL_API}files/profile_pictures/${
    userData?.profile_image ?? "Space/046-rocket.svg"
  }`;

  return (
    <img
      src={profileImageUrl}
      alt="User"
      className={className ?? "h-6 w-6 shrink-0 focus-visible:outline-0"}
    />
  );
}
