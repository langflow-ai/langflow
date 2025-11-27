import { IconsProps } from "./Icons";

export const FileIcon = ({
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
      viewBox={viewBox ? viewBox : "0 0 16 16"}
      width={width ? width : "16"}
      height={height ? height : "16"}
      fill={fill ? fill : "none"}
    >
      <path
        xmlns="http://www.w3.org/2000/svg"
        d="M1 8.2V5.8C1 3.5374 1 2.4058 1.71622 1.7032C2.43183 1 3.58439 1 5.88889 1H7.11111C9.41561 1 10.5682 1 11.2838 1.7032C11.6834 2.095 11.8601 2.62 11.9377 3.4M12 5.8V8.2C12 10.4626 12 11.5942 11.2838 12.2968C10.5682 13 9.41561 13 7.11111 13H5.88889C3.58439 13 2.43183 13 1.71622 12.2968C1.31656 11.905 1.13994 11.38 1.06233 10.6M4.05556 8.2H7.11111M4.05556 5.8H4.66667M8.94444 5.8H6.5"
        stroke="currentColor"
        strokeLinecap="round"
      />
    </svg>
  );
};
