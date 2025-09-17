import { Bot, Check } from "lucide-react";
import React from "react";

export interface GenericIconProps {
  name: string;
  className?: string;
  strokeWidth?: number;
}

// Simple icon mapping - extend as needed
const iconMap = {
  Bot,
  Check,
  bot: Bot,
  check: Check,
};

export function GenericIcon({
  name,
  className,
  strokeWidth = 1.5,
}: GenericIconProps) {
  const IconComponent = iconMap[name as keyof typeof iconMap] || Bot;

  return <IconComponent className={className} strokeWidth={strokeWidth} />;
}
