const SvgAtomicChat = ({ isDark = false, ...props }) => {
  const primary = isDark ? "#FFFFFF" : "#111827";
  const accent = "#6366F1";

  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <circle cx="32" cy="32" r="28" stroke={accent} strokeWidth="3" />
      <ellipse
        cx="32"
        cy="32"
        rx="28"
        ry="10"
        stroke={accent}
        strokeWidth="2.5"
      />
      <ellipse
        cx="32"
        cy="32"
        rx="28"
        ry="10"
        stroke={accent}
        strokeWidth="2.5"
        transform="rotate(60 32 32)"
      />
      <ellipse
        cx="32"
        cy="32"
        rx="28"
        ry="10"
        stroke={accent}
        strokeWidth="2.5"
        transform="rotate(120 32 32)"
      />
      <circle cx="32" cy="32" r="5" fill={accent} />
      <text
        x="32"
        y="58"
        textAnchor="middle"
        fontSize="9"
        fontFamily="ui-sans-serif, system-ui, sans-serif"
        fill={primary}
      >
        AC
      </text>
    </svg>
  );
};

export default SvgAtomicChat;
