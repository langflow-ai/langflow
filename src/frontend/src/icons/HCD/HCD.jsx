import { stringToBool } from "@/utils/utils";

const HCDSVG = (props) => (
  <svg
    width="96"
    height="96"
    viewBox="12 33 72 29"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    {...props}
  >
    <g clipPath="url(#clip0_702_1449)">
      {/* <rect width="96" height="96" rx="6" fill="white"/> */}
      <path
        d="M38.0469 33H12V62.1892H38.0469L44.5902 57.1406V38.0485L38.0469 33ZM17.0478 38.0485H39.5424V57.1459H17.0478V38.0485Z"
        fill={stringToBool(props.isdark) ? "#ffffff" : "#0A0A0A"}
      />
      <path
        d="M82.0705 38.2605V33.3243H58.2546L51.788 38.2605V45.038L58.2546 49.9742H79.0107V56.9286H53.076V61.8648H77.5334L84 56.9286V49.9742L77.5334 45.038H56.7772V38.2605H82.0705Z"
        fill={stringToBool(props.isdark) ? "#ffffff" : "#0A0A0A"}
      />
    </g>
    <defs>
      <clipPath id="clip0_702_1449">
        <rect width="96" height="96" fill="white" />
      </clipPath>
    </defs>
  </svg>
);
export default HCDSVG;
