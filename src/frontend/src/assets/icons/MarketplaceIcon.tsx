import { IconsProps } from "./Icons";

export const MarketplaceIcon = ({
  className,
  fill,
  width,
  height,
  viewBox,
}: IconsProps) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      viewBox={viewBox ? viewBox : "0 0 14 14"}
      width={width ? width : "14"}
      height={height ? height : "14"}
      fill={fill ? fill : "none"}
    >
      <rect
        x="0.5"
        y="2.88708"
        width="5.34417"
        height="5.34416"
        stroke="currentColor"
      />
      <rect
        x="0.5"
        y="8.15576"
        width="5.34417"
        height="5.34416"
        stroke="currentColor"
      />
      <rect
        x="8.06299"
        y="0.5"
        width="5.34417"
        height="5.34416"
        stroke="currentColor"
      />
      <rect
        x="5.90161"
        y="8.15576"
        width="5.34417"
        height="5.34416"
        stroke="currentColor"
      />
    </svg>
  );
};
