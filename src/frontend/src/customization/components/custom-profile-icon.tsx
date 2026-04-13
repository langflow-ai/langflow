import { ProfileIcon } from "@/components/core/appHeaderComponent/components/ProfileIcon";

interface CustomProfileIconProps {
  className?: string;
}

export function CustomProfileIcon({ className }: CustomProfileIconProps = {}) {
  return <ProfileIcon className={className} />;
}

export default CustomProfileIcon;
