import * as fa from "react-icons/fa";
import * as faV6 from "react-icons/fa6";

export const fontAwesomeIcons = {
  FaApple: fa.FaApple,
  FaDiscord: fa.FaDiscord,
  FaGithub: fa.FaGithub,
};

export const isFontAwesomeIcon = (name: string): boolean => {
  return name.startsWith("Fa") && fontAwesomeIcons[name] !== undefined;
};
