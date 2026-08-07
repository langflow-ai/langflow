/**
 * Tells whether a synthetic event was raised inside a React portal instead of
 * inside the element the handler is attached to.
 *
 * React propagates events through the React tree, not the DOM tree, so an
 * overlay opened from a node (dialog, popover, dropdown) still bubbles its
 * events up to the canvas handlers even though its DOM lives outside the node.
 * Comparing the event target with the handler's element separates the two.
 *
 * @see https://react.dev/reference/react-dom/createPortal
 */
const isEventFromPortal = (event: React.SyntheticEvent): boolean => {
  const target = event.target as Node | null;
  return !!target && !event.currentTarget.contains(target);
};

export default isEventFromPortal;
