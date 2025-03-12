export interface Actor {
  id: string;
  entity_type: "user" | "flow";
  entity_id: string;
  name?: string; // This comes from the backend via the ActorRead model
}
