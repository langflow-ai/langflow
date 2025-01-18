import KendraLabsLogo from "@/assets/KendraLabsLogo200x200.png";
import ChainLogo from "@/assets/logo.svg?react";
import { ENABLE_NEW_LOGO } from "@/customization/feature-flags";
import React from "react";

interface LogoProps {
  title?: string;
  className?: string;
  chainClassName?: string;
  alt?: string;
}

const Logo: React.FC<LogoProps> = ({
  title = "Kendra Labs Logo",
  className = "absolute h-[18px] w-[18px]",
  chainClassName = "absolute h-[18px] w-[18px]",
  alt = "Kendra Labs Logo",
}) => {
  return ENABLE_NEW_LOGO ? (
    <img src={KendraLabsLogo} className={className} alt={alt} />
  ) : (
    <ChainLogo title={title} className={chainClassName} />
  );
};

export default Logo;
