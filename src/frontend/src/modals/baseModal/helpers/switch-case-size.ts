export const switchCaseModalSize = (size: string) => {
  let minWidth: string;
  let height: string;
  switch (size) {
    case "notice":
      minWidth = "min-w-[400px] max-w-[400px]";
      height = "";
      break;
    case "x-small":
      minWidth = "min-w-[20vw]";
      height = "";
      break;
    case "smaller":
      minWidth = "min-w-[40vw]";
      height = "h-[11rem]";
      break;
    case "smaller-h-full":
      minWidth = "min-w-[40vw]";
      height = "";
      break;
    case "small-update":
      minWidth = "min-w-[480px] max-w-[480px]";
      height = "";
      break;
    case "small":
      minWidth = "min-w-[40vw]";
      height = "h-[40vh]";
      break;
    case "small-query":
      minWidth = "min-w-[35vw]";
      height = "h-fit";
      break;
    case "medium-small-tall":
      minWidth = "w-[900px] max-w-[98vw]";
      height = "h-[70vh]";
      break;
    case "small-h-full":
      minWidth = "min-w-[40vw]";
      height = "";
      break;
    case "medium":
      minWidth = "min-w-[60vw] max-w-[720px]";
      height = "h-[60vh]";
      break;
    case "medium-tall":
      minWidth = "min-w-[60vw]";
      height = "h-[90vh]";
      break;
    case "medium-h-full":
      minWidth = "min-w-[60vw]";
      height = "";
      break;
    case "large":
      minWidth = "min-w-[85vw]";
      height = "h-[80vh]";
      break;
    case "templates":
      minWidth = "w-[97vw] max-w-[1200px]";
      height =
        "min-h-[700px] lg:min-h-0 h-[90vh] md:h-[80vh] lg:h-[50vw] lg:max-h-[620px]";
      break;
    case "three-cards":
      minWidth = "min-w-[1066px]";
      height = "max-h-[94vh]";
      break;
    case "large-thin":
      minWidth = "min-w-[65vw]";
      height = "h-[90vh]";
      break;

    case "md-thin":
      minWidth = "min-w-[85vw]";
      height = "h-[90vh]";
      break;

    case "sm-thin":
      minWidth = "min-w-[65vw]";
      height = "h-[90vh]";
      break;

    case "large-h-full":
      minWidth = "min-w-[80vw]";
      height = "";
      break;

    case "x-large":
      minWidth = "min-w-[95vw]";
      height = "h-[95vh]";
      break;

    case "retangular":
      minWidth = "!min-w-[900px]";
      height = "min-h-[232px]";
      break;

    default:
      minWidth = "min-w-[80vw]";
      height = "h-[90vh]";
      break;
  }
  return { minWidth, height };
};
