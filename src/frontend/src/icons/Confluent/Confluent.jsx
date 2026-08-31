// Stylized Confluent mark: a ring of arc segments (the "C" of the Confluent
// logo family), in Confluent's brand blue.  Kept geometric so it stays crisp
// at sidebar sizes and readable on both light and dark grounds.
const SvgConfluent = ({ isDark, ...props }) => {
  const stroke = isDark ? "#7DA6FF" : "#173361";
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* outer ring segments */}
      <path
        d="M22.36 6.9A11 11 0 0 1 27 16"
        stroke={stroke}
        strokeWidth="3.2"
        strokeLinecap="round"
      />
      <path
        d="M27 16a11 11 0 0 1-4.64 9.1"
        stroke={stroke}
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeOpacity="0.85"
      />
      <path
        d="M16 27A11 11 0 0 1 5 16"
        stroke={stroke}
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeOpacity="0.7"
      />
      <path
        d="M5 16A11 11 0 0 1 16 5"
        stroke={stroke}
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeOpacity="0.55"
      />
      {/* inner ring segments */}
      <path
        d="M16 10.4a5.6 5.6 0 0 1 5.6 5.6"
        stroke={stroke}
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeOpacity="0.85"
      />
      <path
        d="M10.4 16a5.6 5.6 0 0 1 5.6-5.6"
        stroke={stroke}
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeOpacity="0.55"
      />
      <path
        d="M16 21.6a5.6 5.6 0 0 1-5.6-5.6"
        stroke={stroke}
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeOpacity="0.7"
      />
    </svg>
  );
};

export default SvgConfluent;
