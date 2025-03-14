import LangflowLogo from "@/assets/LangflowLogo.svg?react";

export default function LogoIcon() {
  return (
    <div className="bg-muted relative flex h-8 w-8 items-center justify-center rounded-md">
      <div className="flex h-8 w-8 items-center justify-center">
        <LangflowLogo
          title="Langflow Logo"
          className="absolute h-[18px] w-[18px]"
        />
      </div>
    </div>
  );
}
