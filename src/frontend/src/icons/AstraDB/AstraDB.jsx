import { stringToBool } from "@/utils/utils";

const AstraSVG = (props) => (
  <svg
    {...props}
    width="167"
    height="68"
    viewBox="0 0 167 68"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M60.2338 0.25H0.000244141V67.75H60.2338L75.365 56.0752V11.9248L60.2338 0.25ZM11.6732 11.9248H63.692V56.0874H11.6732V11.9248Z"
      fill={stringToBool(props.isdark) ? "#ffffff" : "#0A0A0A"}
    />
    <path
      d="M162.038 12.415V1H106.964L92.0097 12.415V28.088L106.964 39.503H154.962V55.585H94.9883V67H151.546L166.5 55.585V39.503L151.546 28.088H103.547V12.415H162.038Z"
      fill={stringToBool(props.isdark) ? "#ffffff" : "#0A0A0A"}
    />
  </svg>
);
export default AstraSVG;
