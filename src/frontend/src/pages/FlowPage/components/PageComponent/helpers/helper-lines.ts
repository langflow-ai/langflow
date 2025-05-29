import { Node, XYPosition } from "@xyflow/react";

export interface HelperLine {
  id: string;
  position: number;
  orientation: "horizontal" | "vertical";
}

export interface HelperLinesState {
  horizontal?: HelperLine;
  vertical?: HelperLine;
}

const SNAP_DISTANCE = 5;

export function getHelperLines(
  draggingNode: Node,
  nodes: Node[],
  nodeWidth = 150,
  nodeHeight = 50,
): HelperLinesState {
  const helperLines: HelperLinesState = {};

  // Get the dragging node bounds
  const draggingNodeBounds = {
    left: draggingNode.position.x,
    right:
      draggingNode.position.x + (draggingNode.measured?.width || nodeWidth),
    top: draggingNode.position.y,
    bottom:
      draggingNode.position.y + (draggingNode.measured?.height || nodeHeight),
    centerX:
      draggingNode.position.x + (draggingNode.measured?.width || nodeWidth) / 2,
    centerY:
      draggingNode.position.y +
      (draggingNode.measured?.height || nodeHeight) / 2,
  };

  const otherNodes = nodes.filter((node) => node.id !== draggingNode.id);

  // Check for vertical alignment (horizontal lines)
  for (const node of otherNodes) {
    const nodeBounds = {
      left: node.position.x,
      right: node.position.x + (node.measured?.width || nodeWidth),
      top: node.position.y,
      bottom: node.position.y + (node.measured?.height || nodeHeight),
      centerX: node.position.x + (node.measured?.width || nodeWidth) / 2,
      centerY: node.position.y + (node.measured?.height || nodeHeight) / 2,
    };

    // Check top alignment
    if (Math.abs(draggingNodeBounds.top - nodeBounds.top) < SNAP_DISTANCE) {
      helperLines.horizontal = {
        id: `horizontal-top-${node.id}`,
        position: nodeBounds.top,
        orientation: "horizontal",
      };
    }

    // Check bottom alignment
    if (
      Math.abs(draggingNodeBounds.bottom - nodeBounds.bottom) < SNAP_DISTANCE
    ) {
      helperLines.horizontal = {
        id: `horizontal-bottom-${node.id}`,
        position: nodeBounds.bottom,
        orientation: "horizontal",
      };
    }

    // Check center alignment
    if (
      Math.abs(draggingNodeBounds.centerY - nodeBounds.centerY) < SNAP_DISTANCE
    ) {
      helperLines.horizontal = {
        id: `horizontal-center-${node.id}`,
        position: nodeBounds.centerY,
        orientation: "horizontal",
      };
    }
  }

  // Check for horizontal alignment (vertical lines)
  for (const node of otherNodes) {
    const nodeBounds = {
      left: node.position.x,
      right: node.position.x + (node.measured?.width || nodeWidth),
      top: node.position.y,
      bottom: node.position.y + (node.measured?.height || nodeHeight),
      centerX: node.position.x + (node.measured?.width || nodeWidth) / 2,
      centerY: node.position.y + (node.measured?.height || nodeHeight) / 2,
    };

    // Check left alignment
    if (Math.abs(draggingNodeBounds.left - nodeBounds.left) < SNAP_DISTANCE) {
      helperLines.vertical = {
        id: `vertical-left-${node.id}`,
        position: nodeBounds.left,
        orientation: "vertical",
      };
    }

    // Check right alignment
    if (Math.abs(draggingNodeBounds.right - nodeBounds.right) < SNAP_DISTANCE) {
      helperLines.vertical = {
        id: `vertical-right-${node.id}`,
        position: nodeBounds.right,
        orientation: "vertical",
      };
    }

    // Check center alignment
    if (
      Math.abs(draggingNodeBounds.centerX - nodeBounds.centerX) < SNAP_DISTANCE
    ) {
      helperLines.vertical = {
        id: `vertical-center-${node.id}`,
        position: nodeBounds.centerX,
        orientation: "vertical",
      };
    }
  }

  return helperLines;
}

export function getSnapPosition(
  draggingNode: Node,
  nodes: Node[],
  nodeWidth = 150,
  nodeHeight = 50,
): XYPosition {
  const helperLines = getHelperLines(
    draggingNode,
    nodes,
    nodeWidth,
    nodeHeight,
  );
  let snapPosition = { ...draggingNode.position };

  if (helperLines.horizontal) {
    const draggingNodeBounds = {
      top: draggingNode.position.y,
      bottom:
        draggingNode.position.y + (draggingNode.measured?.height || nodeHeight),
      centerY:
        draggingNode.position.y +
        (draggingNode.measured?.height || nodeHeight) / 2,
    };

    // Snap to the helper line position
    if (helperLines.horizontal.id.includes("top")) {
      snapPosition.y = helperLines.horizontal.position;
    } else if (helperLines.horizontal.id.includes("bottom")) {
      snapPosition.y =
        helperLines.horizontal.position -
        (draggingNode.measured?.height || nodeHeight);
    } else if (helperLines.horizontal.id.includes("center")) {
      snapPosition.y =
        helperLines.horizontal.position -
        (draggingNode.measured?.height || nodeHeight) / 2;
    }
  }

  if (helperLines.vertical) {
    const draggingNodeBounds = {
      left: draggingNode.position.x,
      right:
        draggingNode.position.x + (draggingNode.measured?.width || nodeWidth),
      centerX:
        draggingNode.position.x +
        (draggingNode.measured?.width || nodeWidth) / 2,
    };

    // Snap to the helper line position
    if (helperLines.vertical.id.includes("left")) {
      snapPosition.x = helperLines.vertical.position;
    } else if (helperLines.vertical.id.includes("right")) {
      snapPosition.x =
        helperLines.vertical.position -
        (draggingNode.measured?.width || nodeWidth);
    } else if (helperLines.vertical.id.includes("center")) {
      snapPosition.x =
        helperLines.vertical.position -
        (draggingNode.measured?.width || nodeWidth) / 2;
    }
  }

  return snapPosition;
}
