import type {
  FlowBinding,
  FlowOutputChoice,
  HookBinding,
} from "../../entities";

export const outputKey = (value: FlowBinding) =>
  JSON.stringify([value.flow_id, value.node_id, value.output_name]);

export const bindingOf = ({
  flow_id,
  node_id,
  output_name,
  revision,
}: FlowOutputChoice): FlowBinding => ({
  flow_id,
  node_id,
  output_name,
  revision,
});

export const orderedHooks = (hooks: HookBinding[]) =>
  hooks
    .map((hook, index) => ({ hook, index }))
    .sort(
      (a, b) =>
        (a.hook.priority ?? 0) - (b.hook.priority ?? 0) || a.index - b.index,
    );

export function moveHook(
  hooks: HookBinding[],
  index: number,
  direction: -1 | 1,
): HookBinding[] {
  const sorted = orderedHooks(hooks).map(({ hook }) => hook);
  const destination = index + direction;
  if (destination < 0 || destination >= sorted.length) return hooks;
  [sorted[index], sorted[destination]] = [sorted[destination], sorted[index]];
  // Equal priorities make the saved list the execution order, including imported bindings.
  return sorted.map((hook) => ({ ...hook, priority: 0 }));
}

export const validFlowTimeout = (value: number) =>
  Number.isFinite(value) && value > 0 && value <= 300;

export const validCompactionThreshold = (value: number) =>
  Number.isInteger(value) && value >= 1 && value <= 10_000_000;
