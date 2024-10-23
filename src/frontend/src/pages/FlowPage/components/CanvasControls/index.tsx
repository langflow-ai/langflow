import { ControlButton, Panel, useViewport } from "reactflow"

const CanvasControls = () => {
  const { zoom } = useViewport()

  return (
    <Panel
      position="bottom-left"
    >
      <ControlButton />
    </Panel>
  )
}