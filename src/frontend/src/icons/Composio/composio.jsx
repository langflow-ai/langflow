const Icon = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={32}
    height={32}
    viewBox="0 0 60 63"
    fill="none"
    {...props}
  >
    <path
      fill="#9A4DFF"
      d="M36.232 5H23.989C12.397 5 3 14.766 3 26.813v12.724C3 51.584 12.397 61.35 23.99 61.35h12.242c11.589 0 20.986-9.766 20.986-21.813V26.813C57.218 14.766 47.821 5 36.232 5"
    />
    <path
      fill="url(#a)"
      d="M36.232 5H23.989C12.397 5 3 14.766 3 26.813v12.724C3 51.584 12.397 61.35 23.99 61.35h12.242c11.589 0 20.986-9.766 20.986-21.813V26.813C57.218 14.766 47.821 5 36.232 5"
    />
    <path
      stroke="url(#b)"
      strokeWidth={1.44}
      d="M37.98 5H22.238C11.615 5 3 13.953 3 24.996v16.358C3 52.397 11.612 61.35 22.238 61.35H37.98c10.623 0 19.238-8.953 19.238-19.996V24.996C57.218 13.953 48.606 5 37.98 5Z"
    />
    <mask
      id="c"
      width={28}
      height={28}
      x={16}
      y={19}
      maskUnits="userSpaceOnUse"
      style={{
        maskType: "luminance",
      }}
    >
      <path fill="#fff" d="M16.994 19.542H43.23v27.266H16.994z" />
    </mask>
    <g mask="url(#c)">
      <path
        fill="#fff"
        fillRule="evenodd"
        d="M32.952 20.899a.983.983 0 0 1 .444 1.095l-2.47 9.416h9.012a.9.9 0 0 1 .511.16.95.95 0 0 1 .344.423.99.99 0 0 1-.175 1.044L27.596 47.541a.899.899 0 0 1-1.138.19.95.95 0 0 1-.405-.474 1 1 0 0 1-.036-.633l2.472-9.412h-9.018a.9.9 0 0 1-.507-.159.95.95 0 0 1-.345-.425.99.99 0 0 1 .175-1.044l13.022-14.501a.899.899 0 0 1 1.132-.187"
        clipRule="evenodd"
      />
    </g>
    <defs>
      <linearGradient
        id="a"
        x1={30.109}
        x2={30.109}
        y1={6.818}
        y2={59.532}
        gradientUnits="userSpaceOnUse"
      >
        <stop stopColor="#9A4DFF" />
        <stop offset={0.31} stopColor="#8017F7" />
        <stop offset={0.425} stopColor="#7A20E1" />
        <stop offset={0.495} stopColor="#7A20E1" />
        <stop offset={0.665} stopColor="#7C16F8" />
        <stop offset={1} stopColor="#8222FF" />
      </linearGradient>
      <linearGradient
        id="b"
        x1={30.109}
        x2={30.109}
        y1={6.817}
        y2={59.533}
        gradientUnits="userSpaceOnUse"
      >
        <stop stopColor="#6F00FF" stopOpacity={0.18} />
        <stop offset={1} stopColor="#600ED1" />
      </linearGradient>
    </defs>
  </svg>
);
export default Icon;
