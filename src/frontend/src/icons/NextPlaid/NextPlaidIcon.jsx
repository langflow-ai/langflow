const NextPlaidIcon = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={24}
    height={24}
    viewBox="0 0 24 24"
    fill="none"
    style={{ backgroundColor: "#1a1a2e", borderRadius: "6px" }}
    {...props}
  >
    {/* Simple multi-vector / matrix icon representing ColBERT */}
    <g transform="translate(4, 4)">
      <rect
        x="0"
        y="0"
        width="4"
        height="4"
        rx="1"
        fill={props.isdark === "true" ? "white" : "#7c3aed"}
      />
      <rect
        x="6"
        y="0"
        width="4"
        height="4"
        rx="1"
        fill={props.isdark === "true" ? "white" : "#7c3aed"}
      />
      <rect
        x="12"
        y="0"
        width="4"
        height="4"
        rx="1"
        fill={props.isdark === "true" ? "white" : "#7c3aed"}
      />
      <rect
        x="0"
        y="6"
        width="4"
        height="4"
        rx="1"
        fill={props.isdark === "true" ? "white" : "#a78bfa"}
      />
      <rect
        x="6"
        y="6"
        width="4"
        height="4"
        rx="1"
        fill={props.isdark === "true" ? "white" : "#a78bfa"}
      />
      <rect
        x="12"
        y="6"
        width="4"
        height="4"
        rx="1"
        fill={props.isdark === "true" ? "white" : "#a78bfa"}
      />
      <rect
        x="0"
        y="12"
        width="4"
        height="4"
        rx="1"
        fill={props.isdark === "true" ? "white" : "#7c3aed"}
      />
      <rect
        x="6"
        y="12"
        width="4"
        height="4"
        rx="1"
        fill={props.isdark === "true" ? "white" : "#7c3aed"}
      />
      <rect
        x="12"
        y="12"
        width="4"
        height="4"
        rx="1"
        fill={props.isdark === "true" ? "white" : "#7c3aed"}
      />
    </g>
  </svg>
);

export default NextPlaidIcon;
