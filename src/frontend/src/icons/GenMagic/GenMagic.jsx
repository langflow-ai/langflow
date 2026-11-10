const PETAL =
  "M64 57 C69 48 74 35 74 24 A10 10 0 1 0 54 24 C54 35 59 48 64 57 Z";
const ROTATIONS = [0, 72, 144, 216, 288];

const SvgGenMagic = ({ isDark = false, ...props }) => {
  const color = isDark ? "#5B9BF8" : "#1D74F5";

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="1em"
      height="1em"
      viewBox="0 0 128 128"
      fill="none"
      {...props}
    >
      <rect
        width="128"
        height="128"
        rx="28"
        fill={color}
        fillOpacity={isDark ? 0.16 : 0.1}
      />
      {ROTATIONS.map((angle) => (
        <path
          key={angle}
          d={PETAL}
          fill={color}
          transform={`rotate(${angle} 64 64)`}
        />
      ))}
    </svg>
  );
};

export default SvgGenMagic;
