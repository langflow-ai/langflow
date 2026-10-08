const SvgGetYouTubeTranscript = ({ isDark: _isDark, ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 500 500"
    fill="none"
    {...props}
  >
    <defs>
      <linearGradient
        id="getyoutubetranscript-bg"
        x1="250"
        y1="0"
        x2="250"
        y2="500"
        gradientUnits="userSpaceOnUse"
      >
        <stop stopColor="#EF4444" />
        <stop offset="1" stopColor="#B91C1C" />
      </linearGradient>
    </defs>
    <rect
      width="500"
      height="500"
      rx="110"
      fill="url(#getyoutubetranscript-bg)"
    />
    <g fill="#fff">
      <rect x="100" y="121" width="300" height="38" rx="19" />
      <rect x="100" y="195" width="260" height="38" rx="19" />
      <rect x="100" y="268" width="300" height="38" rx="19" />
      <rect x="100" y="342" width="170" height="38" rx="19" />
    </g>
  </svg>
);

export default SvgGetYouTubeTranscript;
