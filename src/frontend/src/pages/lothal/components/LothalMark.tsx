// Lothal mark — a paper boat. Lothal was an ancient dockyard where ships were
// built; this app is the modern drydock for software. Inherits `currentColor`.

export function LothalMark({ size = 22 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      role="img"
      aria-label="Lothal"
      style={{ display: "block" }}
    >
      {/* Sail */}
      <path d="M16 5 L23 17 L9 17 Z" fill="currentColor" />
      {/* Hull (paper-boat trapezoid) */}
      <path d="M3 17 L29 17 L24 25 L8 25 Z" fill="currentColor" />
      {/* Water flicks */}
      <path
        d="M2 26 Q5 25 7 26"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        fill="none"
        opacity="0.55"
      />
      <path
        d="M25 26 Q28 25 30 26"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        fill="none"
        opacity="0.55"
      />
    </svg>
  );
}
