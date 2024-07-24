import { cn } from "../../utils/utils";

const FreezeAllSvg = ({ className, ...props }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      version="1.2"
      viewBox="0 0 24 24"
      className={cn("h-4 w-4 stroke-[1.5]", className)}
      {...props}
    >
      <title>snowflake-svg</title>
      <path
        id="Layer copy"
        className="fill-none stroke-current"
        d="m6 22.3l-4.4-4.4 4.4-4.3"
      />
      <path id="Layer" className="fill-none stroke-current" d="m11 17.9h-9.4" />
      <path id="Layer" className="fill-none stroke-current" d="m7.8 8.9h14.6" />
      <path
        id="Layer"
        className="fill-none stroke-current"
        d="m15.1 1.6v14.6"
      />
      <path
        id="Layer"
        className="fill-none stroke-current"
        d="m21 11.8l-2.9-2.9 2.9-2.9"
      />
      <path
        id="Layer"
        className="fill-none stroke-current"
        d="m9.3 6l2.9 2.9-2.9 2.9"
      />
      <path
        id="Layer"
        className="fill-none stroke-current"
        d="m18.1 3.1l-3 2.9-2.9-2.9"
      />
      <path
        id="Layer"
        className="fill-none stroke-current"
        d="m12.2 14.8l2.9-3 3 3"
      />
    </svg>
  );
};

export default FreezeAllSvg;
