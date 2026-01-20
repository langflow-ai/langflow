import { useContext } from "react";
import { AuthContext } from "@/contexts/authContext";
import { BASE_URL_API } from "@/customization/config-constants";

type InputMessageProps = {
  content: string;
};

export const InputMessage = ({ content }: InputMessageProps) => {
  const { userData } = useContext(AuthContext);

  const profileImageUrl = `${BASE_URL_API}files/profile_pictures/${
    userData?.profile_image ?? "Space/046-rocket.svg"
  }`;

  return (
    <div className="flex items-center gap-2">
      <img
        src={profileImageUrl}
        alt="User"
        className="h-4 w-4 flex-shrink-0 rounded-full"
      />
      <div className="whitespace-pre-wrap font-mono text-sm text-accent-emerald-foreground">
        {content}
      </div>
    </div>
  );
};
