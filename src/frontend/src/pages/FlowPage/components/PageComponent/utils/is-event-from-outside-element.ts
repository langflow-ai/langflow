/**
 * Tells whether a synthetic event originated outside the element its handler is
 * attached to, by comparing the event target with that element. Layout does not
 * take part: neither `position` nor `pointer-events` is consulted.
 *
 * A portal is what produces that situation here. React propagates events through
 * the React tree, not the DOM tree, so an overlay opened from a node (dialog,
 * popover, dropdown) still bubbles its events up to the canvas handlers even
 * though its DOM lives outside the node — and it is the only way an event can
 * reach a node handler with a target outside the node's own DOM.
 *
 * @see https://react.dev/reference/react-dom/createPortal
 */
const isEventFromOutsideElement = (event: React.SyntheticEvent): boolean => {
  const target = event.target as Node | null;
  return !!target && !event.currentTarget.contains(target);
};

export default isEventFromOutsideElement;
