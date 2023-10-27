import React, { ReactNode } from "react";

interface ElementStackProps {
  children: ReactNode[];
}

const ElementStack: React.FC<ElementStackProps> = ({ children }) => {
  return (
    <div className="relative flex">
      {children.map((child, index) => (
        <div
          key={index}
          className={` transform translate-x-${index * 4} -translate-y-${
            index * 2
          } scale-${100 - index * 3}`}
          style={{ zIndex: children.length - index }}
        >
          {child}
        </div>
      ))}
    </div>
  );
};

export default ElementStack;
