import { AuthContext } from "@/contexts/authContext";
import { BASE_URL_API } from "@/customization/config-constants";
import { useContext } from "react";

export function ProfileIcon() {
  const { userData } = useContext(AuthContext);

  const profileImageUrl = `${BASE_URL_API}files/profile_pictures/${
    userData?.profile_image ?? "Space/046-rocket.svg"
  }`;

  return (
    <div className="group relative aspect-square h-full w-full overflow-hidden">
      <div className="absolute inset-0 z-10 rounded-full bg-gradient-to-tr from-primary/20 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
      <img
        src={profileImageUrl}
        alt={userData?.username ?? "Profile"}
        className="h-full w-full rounded-full object-cover transition-transform duration-300 group-hover:scale-110"
        loading="lazy"
      />
      <div className="absolute inset-0 rounded-full ring-1 ring-border/50 transition-all duration-300 group-hover:ring-2 group-hover:ring-border" />
    </div>
  );
}
