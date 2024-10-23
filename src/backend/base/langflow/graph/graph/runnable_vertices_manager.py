from collections import defaultdict


class RunnableVerticesManager:
    def __init__(self) -> None:
        self.run_map: dict[str, list[str]] = defaultdict(list)  # Tracks successors of each vertex
        self.run_predecessors: dict[str, set[str]] = defaultdict(set)  # Tracks predecessors for each vertex
        self.vertices_to_run: set[str] = set()  # Set of vertices that are ready to run
        self.vertices_being_run: set[str] = set()  # Set of vertices that are currently running

    def to_dict(self) -> dict:
        return {
            "run_map": self.run_map,
            "run_predecessors": self.run_predecessors,
            "vertices_to_run": self.vertices_to_run,
            "vertices_being_run": self.vertices_being_run,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunnableVerticesManager":
        instance = cls()
        instance.run_map = data["run_map"]
        instance.run_predecessors = data["run_predecessors"]
        instance.vertices_to_run = data["vertices_to_run"]
        instance.vertices_being_run = data["vertices_being_run"]
        return instance

    def __getstate__(self) -> object:
        return {
            "run_map": self.run_map,
            "run_predecessors": self.run_predecessors,
            "vertices_to_run": self.vertices_to_run,
            "vertices_being_run": self.vertices_being_run,
        }

    def __setstate__(self, state: dict) -> None:
        self.run_map = state["run_map"]
        self.run_predecessors = state["run_predecessors"]
        self.vertices_to_run = state["vertices_to_run"]
        self.vertices_being_run = state["vertices_being_run"]

    def all_predecessors_are_fulfilled(self) -> bool:
        return all(not value for value in self.run_predecessors.values())

    def update_run_state(self, run_predecessors: dict, vertices_to_run: set) -> None:
        self.run_predecessors.update(run_predecessors)
        self.vertices_to_run.update(vertices_to_run)
        self.build_run_map(self.run_predecessors, self.vertices_to_run)

    def is_vertex_runnable(self, vertex_id: str, *, is_active: bool) -> bool:
        """Determines if a vertex is runnable."""
        if not is_active:
            return False
        if vertex_id in self.vertices_being_run:
            return False
        if vertex_id not in self.vertices_to_run:
            return False
        return self.are_all_predecessors_fulfilled(vertex_id)

    def are_all_predecessors_fulfilled(self, vertex_id: str) -> bool:
        return not any(self.run_predecessors.get(vertex_id, []))

    def remove_from_predecessors(self, vertex_id: str) -> None:
        """Removes a vertex from the predecessor list of its successors."""
        predecessors = self.run_map.get(vertex_id, [])
        for predecessor in predecessors:
            if vertex_id in self.run_predecessors[predecessor]:
                self.run_predecessors[predecessor].remove(vertex_id)

    def build_run_map(self, predecessor_map, vertices_to_run) -> None:
        """Builds a map of vertices and their runnable successors."""
        self.run_map = defaultdict(list)
        for vertex_id, predecessors in predecessor_map.items():
            for predecessor in predecessors:
                self.run_map[predecessor].append(vertex_id)
        self.run_predecessors = predecessor_map.copy()
        self.vertices_to_run = vertices_to_run

    def update_vertex_run_state(self, vertex_id: str, *, is_runnable: bool) -> None:
        """Updates the runnable state of a vertex."""
        if is_runnable:
            self.vertices_to_run.add(vertex_id)
        else:
            self.vertices_being_run.discard(vertex_id)

    def remove_vertex_from_runnables(self, v_id) -> None:
        self.update_vertex_run_state(v_id, is_runnable=False)
        self.remove_from_predecessors(v_id)

    def add_to_vertices_being_run(self, v_id) -> None:
        self.vertices_being_run.add(v_id)
