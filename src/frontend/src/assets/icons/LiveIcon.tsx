import { IconsProps } from "./Icons";

export const LiveIcon = ({
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
      viewBox={viewBox ? viewBox : '0 0 12 12'}
      width={width ? width : '12'}
      height={height ? height : '12'}
      fill={fill ? fill : 'none'}
    >
        <path d="M0 6C0 2.6865 2.6865 0 6 0C9.3135 0 12 2.6865 12 6C12 9.3135 9.3135 12 6 12C2.688 11.996 0.004 9.3115 0 6ZM1.2 6C1.2 8.651 3.349 10.8 6 10.8C8.651 10.8 10.8 8.651 10.8 6C10.8 3.349 8.651 1.2 6 1.2C3.3505 1.203 1.203 3.351 1.2 6ZM3.2 6C3.2 5.25739 3.495 4.5452 4.0201 4.0201C4.5452 3.495 5.25739 3.2 6 3.2C6.74261 3.2 7.4548 3.495 7.9799 4.0201C8.505 4.5452 8.8 5.25739 8.8 6C8.8 6.74261 8.505 7.4548 7.9799 7.9799C7.4548 8.505 6.74261 8.8 6 8.8C5.25739 8.8 4.5452 8.505 4.0201 7.9799C3.495 7.4548 3.2 6.74261 3.2 6Z" fill="#3FA33C"/>    </svg>
  );
};
