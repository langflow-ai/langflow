import { cn } from "@/utils/utils";
import { ReactNode } from "react";
import { BorderBeam } from "../../../components/ui/border-beams";

interface EnhancedBeamEffectProps {
  children: ReactNode;
  className?: string;
  primaryColor?: string;
  secondaryColor?: string;
  size?: number;
}

export const EnhancedBeamEffect = ({
  children,
  className,
  primaryColor = "#C661B8",
  secondaryColor = "#61C6B8",
  size = 200,
}: EnhancedBeamEffectProps) => {
  return (
    <div
      className={cn(
        "relative flex items-center justify-center overflow-hidden rounded-xl",
        className,
      )}
    >
      {children}

      {/* Primary beam - larger, slower rotation */}
      <BorderBeam
        duration={12}
        size={size}
        className="opacity-80"
        colorFrom={primaryColor}
        colorTo={secondaryColor}
        anchor={50}
        borderWidth={1.5}
      />

      {/* Secondary beam - smaller, faster rotation in opposite direction */}
      <BorderBeam
        duration={8}
        size={size * 0.85}
        className="opacity-60"
        colorFrom={secondaryColor}
        colorTo={primaryColor}
        anchor={30}
        borderWidth={1}
        delay={2}
      />

      {/* Accent beam - smallest, fastest rotation */}
      <BorderBeam
        duration={18}
        size={size * 1.2}
        className="opacity-40"
        colorFrom={primaryColor}
        colorTo="transparent"
        anchor={70}
        borderWidth={0.8}
        delay={5}
      />

      {/* Highlight beam - occasional pulse */}
      <BorderBeam
        duration={24}
        size={size * 0.95}
        className="opacity-70"
        colorFrom="white"
        colorTo="transparent"
        anchor={10}
        borderWidth={0.5}
        delay={8}
      />
    </div>
  );
};

export default EnhancedBeamEffect;
