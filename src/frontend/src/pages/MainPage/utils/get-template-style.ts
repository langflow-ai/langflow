import { TEMPLATES_DATA } from "../constants";

export const getTemplateStyle = (flowData: {
  name: string;
}): { icon: string; icon_bg_color: string } => {
  const { icon, icon_bg_color } = TEMPLATES_DATA.examples.find((example) =>
    flowData.name.includes(example.name),
  ) ?? { icon: "circle-help", icon_bg_color: "bg-purple-300" };
  return { icon, icon_bg_color };
};
