from collections import defaultdict


class RunnableVerticesManager:
    def __init__(self) -> None:
        self.run_map: dict[str, list[str]] = defaultdict(list)  # Tracks successors of each vertex
        self.run_predecessors: dict[str, set[str]] = defaultdict(
            set
        )  # Tracks predecessors for each vertex, using sets for O(1) ops
        self.vertices_to_run: set[str] = set()  # Set of vertices that are ready to run
        self.vertices_being_run: set[str] = set()  # Set of vertices that are currently running
        self.cycle_vertices: set[str] = set()  # Set of vertices that are in a cycle
        self.ran_at_least_once: set[str] = set()  # Set of vertices that have been run at least once

    def to_dict(self) -> dict:
        return {
            "run_map": self.run_map,
            "run_predecessors": self.run_predecessors,
            "vertices_to_run": self.vertices_to_run,
            "vertices_being_run": self.vertices_being_run,
            "ran_at_least_once": self.ran_at_least_once,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunnableVerticesManager":
        instance = cls()
        instance.run_map = data["run_map"]
        instance.run_predecessors = data["run_predecessors"]
        instance.vertices_to_run = data["vertices_to_run"]
        instance.vertices_being_run = data["vertices_being_run"]
        instance.ran_at_least_once = data.get("ran_at_least_once", set())
        return instance

    def __getstate__(self) -> object:
        return {
            "run_map": self.run_map,
            "run_predecessors": self.run_predecessors,
            "vertices_to_run": self.vertices_to_run,
            "vertices_being_run": self.vertices_being_run,
            "ran_at_least_once": self.ran_at_least_once,
        }

    def __setstate__(self, state: dict) -> None:
        self.run_map = state["run_map"]
        self.run_predecessors = state["run_predecessors"]
        self.vertices_to_run = state["vertices_to_run"]
        self.vertices_being_run = state["vertices_being_run"]
        self.ran_at_least_once = state["ran_at_least_once"]

    def all_predecessors_are_fulfilled(self) -> bool:
        return all(not value for value in self.run_predecessors.values())

    def update_run_state(self, run_predecessors: dict, vertices_to_run: set) -> None:
        self.run_predecessors.update(run_predecessors)
        self.vertices_to_run.update(vertices_to_run)
        self.build_run_map(self.run_predecessors, self.vertices_to_run)

    def is_vertex_runnable(self, vertex_id: str, *, is_active: bool, is_loop: bool = False) -> bool:
        """Determines if a vertex is runnable based on its active state and predecessor fulfillment."""
        if not is_active:
            return False
        if vertex_id in self.vertices_being_run:
            return False
        if vertex_id not in self.vertices_to_run:
            return False

        return self.are_all_predecessors_fulfilled(vertex_id, is_loop=is_loop)

    def are_all_predecessors_fulfilled(self, vertex_id: str, *, is_loop: bool) -> bool:
        """Determines if all predecessors for a vertex have been fulfilled.

        This method checks if a vertex is ready to run by verifying that either:
        1. It has no pending predecessors that need to complete first
        2. For vertices in cycles, none of its pending predecessors are also cycle vertices
           (which would create a circular dependency)

        Args:
            vertex_id (str): The ID of the vertex to check
            is_loop (bool): Whether the vertex is a loop
        Returns:
            bool: True if all predecessor conditions are met, False otherwise
        """
        pending = self.run_predecessors[vertex_id]
        if not pending:
            return True

        if vertex_id in self.cycle_vertices:
            # pending is always a set; avoid unnecessary copying
            if vertex_id in self.ran_at_least_once:
                # Wait if there are still pending or running predecessors; otherwise allow.
                # We only need to check if pending or any are running.
                if pending or (pending & self.vertices_being_run):
                    return False
                return True

            # FIRST execution of a cycle vertex
            # Allow running **only** if it's a loop AND *all* pending predecessors are cycle vertices
            return is_loop and pending <= self.cycle_vertices

        return False

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
        # Convert predecessor_map values to sets for efficient membership and removals
        self.run_predecessors = defaultdict(set, {k: set(v) for k, v in predecessor_map.items()})
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

    def add_to_cycle_vertices(self, v_id):
        self.cycle_vertices.add(v_id)
