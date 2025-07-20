import * as fa from "react-icons/fa";

export const fontAwesomeIcons = {
  FaApple: fa.FaApple,
  FaDiscord: fa.FaDiscord,
  FaGithub: fa.FaGithub,
  FaLinux: fa.FaLinux,
  FaWindows: fa.FaWindows,
};

export const isFontAwesomeIcon = (name: string): boolean => {
  return name.startsWith("Fa") && fontAwesomeIcons[name] !== undefined;
};
