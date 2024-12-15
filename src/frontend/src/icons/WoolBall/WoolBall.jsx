import * as React from "react";
import { SVGProps, forwardRef } from "react";
import styled from "@emotion/styled";

const EmojiContainer = styled.div`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1em;
  height: 1em;
  font-size: 1.2em;
  line-height: 1;
`;

const SvgWoolBall = (props) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: "1em",
      height: "1em",
      fontSize: "1.2em",
      lineHeight: 1,
    }}
    role="img"
    aria-label="wool ball"
    {...props}
  >
    🧶
  </div>
);

export default SvgWoolBall; 