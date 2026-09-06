const SvgHubris = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    fill="currentColor"
    style={{ flex: "none", lineHeight: "1" }}
    viewBox="0 0 24 24"
    {...props}
  >
    <circle cx={12} cy={12} r={2.4} />
    <g opacity={0.85}>
      <circle cx={12} cy={3.5} r={1.4} />
      <circle cx={20.5} cy={12} r={1.4} />
      <circle cx={12} cy={20.5} r={1.4} />
      <circle cx={3.5} cy={12} r={1.4} />
    </g>
    <g opacity={0.6}>
      <circle cx={18.5} cy={5.5} r={1.1} />
      <circle cx={18.5} cy={18.5} r={1.1} />
      <circle cx={5.5} cy={18.5} r={1.1} />
      <circle cx={5.5} cy={5.5} r={1.1} />
    </g>
    <g opacity={0.4} stroke="currentColor" strokeWidth={0.7}>
      <line x1={12} x2={12} y1={12} y2={3.5} />
      <line x1={12} x2={20.5} y1={12} y2={12} />
      <line x1={12} x2={12} y1={12} y2={20.5} />
      <line x1={12} x2={3.5} y1={12} y2={12} />
    </g>
    <g opacity={0.3} stroke="currentColor" strokeWidth={0.7}>
      <line x1={12} x2={18.5} y1={12} y2={5.5} />
      <line x1={12} x2={18.5} y1={12} y2={18.5} />
      <line x1={12} x2={5.5} y1={12} y2={18.5} />
      <line x1={12} x2={5.5} y1={12} y2={5.5} />
    </g>
  </svg>
);
export default SvgHubris;
