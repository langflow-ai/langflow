import oceanbaseLogo from "@/assets/oceanbase_logo.png";

export const SvgOceanBase = (props) => {
  const { style, ...restProps } = props;
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      xmlnsXlink="http://www.w3.org/1999/xlink"
      version="1"
      viewBox="0 0 200 200"
      width="1em"
      height="1em"
      style={{ ...style, filter: "none" }}
      {...restProps}
    >
      <image
        width="200"
        height="200"
        x="0"
        y="0"
        preserveAspectRatio="xMidYMid meet"
        xlinkHref={oceanbaseLogo}
      ></image>
    </svg>
  );
};

export default SvgOceanBase;
