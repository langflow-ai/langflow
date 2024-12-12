import KendraLabsLogo from "@/assets/KendraLabsLogo200x200.png";
import ChainLogo from "@/assets/logo.svg?react";
import { ENABLE_NEW_LOGO } from "@/customization/feature-flags";

interface LogoIconProps {
  className?: string;
  alt?: string;
}

const LogoIcon: React.FC<LogoIconProps> = ({
  className = "absolute h-[18px] w-[18px]",
  alt = "Kendra Labs Logo",
}) => {
  return (
    <>
      {ENABLE_NEW_LOGO ? (
        <img src={KendraLabsLogo} className={className} alt={alt} />
      ) : (
        <ChainLogo title="Langflow Logo" className={className} />
      )}
    </>
  );
};

export default LogoIcon;
