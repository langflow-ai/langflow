import React from "react";
import {
  INPUT_HANDLER_HOVER,
  OUTPUT_HANDLER_HOVER,
} from "../../../../constants/constants";
import {
  nodeColors,
  nodeIconsLucide,
  nodeNames,
} from "../../../../utils/styleUtils";
import { classNames } from "../../../../utils/utils";

const TooltipRenderComponent = ({ item, index, left }) => {
  const Icon = nodeIconsLucide[item.family] ?? nodeIconsLucide["unknown"];

  return (
    <div
      key={index}
      data-testid={`available-${left ? "input" : "output"}-${item.family}`}
    >
      {index === 0 && (
        <span>{left ? INPUT_HANDLER_HOVER : OUTPUT_HANDLER_HOVER}</span>
      )}
      <span
        key={index}
        className={classNames(
          index > 0 ? "mt-2 flex items-center" : "mt-3 flex items-center",
        )}
      >
        <div
          className="h-5 w-5"
          style={{
            color: nodeColors[item.family],
          }}
        >
          <Icon
            className="h-5 w-5"
            strokeWidth={1.5}
            style={{
              color: nodeColors[item.family] ?? nodeColors.unknown,
            }}
          />
        </div>
        <span
          className="ps-2 text-xs text-foreground"
          data-testid={`tooltip-${nodeNames[item.family] ?? "Other"}`}
        >
          {nodeNames[item.family] ?? "Other"}{" "}
          {item?.display_name && item?.display_name?.length > 0 ? (
            <span
              className="text-xs"
              data-testid={`tooltip-${item?.display_name}`}
            >
              {" "}
              {item.display_name === "" ? "" : " - "}
              {item.display_name.split(", ").length > 2
                ? item.display_name.split(", ").map((el, index) => (
                    <React.Fragment key={el + name}>
                      <span>
                        {index === item.display_name.split(", ").length - 1
                          ? el
                          : (el += `, `)}
                      </span>
                    </React.Fragment>
                  ))
                : item.display_name}
            </span>
          ) : (
            <span className="text-xs" data-testid={`tooltip-${item?.type}`}>
              {" "}
              {item.type === "" ? "" : " - "}
              {item.type.split(", ").length > 2
                ? item.type.split(", ").map((el, index) => (
                    <React.Fragment key={el + name}>
                      <span>
                        {index === item.type.split(", ").length - 1
                          ? el
                          : (el += `, `)}
                      </span>
                    </React.Fragment>
                  ))
                : item.type}
            </span>
          )}
        </span>
      </span>
    </div>
  );
};

export default TooltipRenderComponent;
