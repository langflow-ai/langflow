export default function SvgMengram(props) {
  return (
    <svg
      viewBox="0 0 120 120"
      preserveAspectRatio="xMidYMid meet"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        d="M60 16 Q92 16 96 48 Q100 78 72 88 Q50 96 38 76 Q26 58 46 46 Q62 38 70 52 Q76 64 62 68"
        fill="none"
        stroke={props.isDark ? "#c084fc" : "#a855f7"}
        strokeWidth="10"
        strokeLinecap="round"
      />
      <circle
        cx="62"
        cy="68"
        r="10"
        fill={props.isDark ? "#c084fc" : "#a855f7"}
      />
      <circle
        cx="62"
        cy="68"
        r="4.5"
        fill={props.isDark ? "#1a1a2e" : "#ffffff"}
      />
    </svg>
  );
}
