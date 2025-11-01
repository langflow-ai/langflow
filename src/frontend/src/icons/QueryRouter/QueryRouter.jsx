const SvgQueryRouter = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    fillRule="evenodd"
    clipRule="evenodd"
    imageRendering="optimizeQuality"
    shapeRendering="geometricPrecision"
    textRendering="geometricPrecision"
    viewBox="0 0 512 512"
    width="1em"
    height="1em"
    {...props}
  >
    <circle cx={256} cy={256} r={240} fill="#3B82F6" />
    <text
      x={256}
      y={320}
      fontFamily="Arial, sans-serif"
      fontSize={280}
      fontWeight="bold"
      fill="#FFFFFF"
      textAnchor="middle"
      dominantBaseline="middle"
    >
      Q
    </text>
  </svg>
);

export default SvgQueryRouter;

