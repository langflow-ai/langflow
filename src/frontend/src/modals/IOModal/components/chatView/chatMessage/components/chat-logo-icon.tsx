import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import icon from "@/assets/autonomizeLogo.png";

export default function LogoIcon() {
  return (
    <div className="relative flex h-8 w-8 items-center justify-center rounded-md bg-muted">
      <div className="flex h-8 w-8 items-center justify-center bg-secondary p-2 rounded-md">
        {/* <LangflowLogo
          title="Langflow Logo"
          className="absolute h-[18px] w-[18px]"
        /> */}
        <img src={icon} alt="Autonomize Logo" />
      </div>
    </div>
  );
}
