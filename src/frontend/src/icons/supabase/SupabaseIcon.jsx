const SvgSupabaseIcon = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="1em"
    height="1em"
    style={{
      fill: "none",
    }}
    viewBox="0 0 64 64"
    {...props}
  >
    <path
      d="M37.412 62.937c-1.635 2.059-4.95.93-4.99-1.698l-.575-38.453h25.855c4.683 0 7.295 5.41 4.383 9.077z"
      style={{
        fill: "url(#supabase-icon_svg__a)",
        strokeWidth: 0.57177335,
      }}
    />
    <path
      d="M37.412 62.937c-1.635 2.059-4.95.93-4.99-1.698l-.575-38.453h25.855c4.683 0 7.295 5.41 4.383 9.077z"
      style={{
        fill: "url(#supabase-icon_svg__b)",
        fillOpacity: 0.2,
        strokeWidth: 0.57177335,
      }}
    />
    <path
      d="M26.897 1.063c1.635-2.059 4.95-.93 4.99 1.699l.252 38.452H6.607c-4.683 0-7.295-5.409-4.383-9.077z"
      style={{
        fill: "#3ecf8e",
        strokeWidth: 0.57177335,
      }}
    />
    <defs>
      <linearGradient
        id="supabase-icon_svg__a"
        x1={53.974}
        x2={94.163}
        y1={54.974}
        y2={71.829}
        gradientTransform="matrix(.57177 0 0 .57177 .986 -.12)"
        gradientUnits="userSpaceOnUse"
      >
        <stop stopColor="#249361" />
        <stop offset={1} stopColor="#3ECF8E" />
      </linearGradient>
      <linearGradient
        id="supabase-icon_svg__b"
        x1={36.156}
        x2={54.484}
        y1={30.578}
        y2={65.081}
        gradientTransform="matrix(.57177 0 0 .57177 .986 -.12)"
        gradientUnits="userSpaceOnUse"
      >
        <stop />
        <stop offset={1} stopOpacity={0} />
      </linearGradient>
    </defs>
  </svg>
);
export default SvgSupabaseIcon;
