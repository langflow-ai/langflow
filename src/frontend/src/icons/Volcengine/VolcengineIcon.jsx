const VolcengineSVG = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="1em"
    height="1em"
    viewBox="0 0 48 48"
    fill="none"
    {...props}
  >
    <path
      d="M24 4 6 14v20l18 10 18-10V14L24 4Zm0 4.6 13.9 7.7L24 24 10.1 16.3 24 8.6ZM9.4 19.1 22.4 26v11.3L9.4 30.1V19.1Zm16.2 18.2V26l13-6.9v11L25.6 37.3Z"
      fill={props.isDark ? "#4d7cff" : "#1664ff"}
    />
  </svg>
);

export default VolcengineSVG;
