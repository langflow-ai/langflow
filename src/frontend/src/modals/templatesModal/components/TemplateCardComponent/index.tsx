import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import React from "react";

interface CardData {
  bgImage: string;
  spiralImage: string;
  icon: string;
  category: string;
  title: string;
  description: string;
  onClick: () => void;
}

const TemplateCard: React.FC<CardData> = ({
  bgImage,
  spiralImage,
  icon,
  category,
  title,
  description,
  onClick,
}) => {
  return (
    <Button
      unstyled
      onClick={onClick}
      className="group relative h-full w-full overflow-hidden rounded-3xl border text-left"
    >
      <img
        src={bgImage}
        alt={`${title} Background`}
        className="absolute inset-2 h-[calc(100%-16px)] w-[calc(100%-16px)] rounded-2xl object-cover"
      />
      <div className="absolute inset-2 h-[calc(100%-16px)] w-[calc(100%-16px)] overflow-hidden rounded-2xl">
        <img
          src={spiralImage}
          alt={`${title} Spiral`}
          className="h-full w-full object-cover opacity-25 transition-all duration-300 group-hover:scale-[102%] group-hover:opacity-60"
        />
      </div>
      <div className="card-shine-effect absolute inset-2 flex h-[calc(100%-16px)] w-[calc(100%-16px)] flex-col items-start gap-4 rounded-2xl p-4 py-6 text-white">
        <div className="flex items-center gap-2 text-white mix-blend-overlay">
          <ForwardedIconComponent name={icon} className="h-4 w-4" />
          <span className="font-mono text-xs font-semibold uppercase tracking-wider">
            {category}
          </span>
        </div>
        <h3 className="text-xl font-bold">{title}</h3>
        <p className="text-xs font-medium opacity-90">{description}</p>
      </div>
    </Button>
  );
};

export default TemplateCard;
