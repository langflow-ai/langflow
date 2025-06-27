import asyncio
from collections import defaultdict


class RunnableVerticesManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
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
        self.ran_at_least_once = state.get("ran_at_least_once", set())

    async def all_predecessors_are_fulfilled(self) -> bool:
        async with self._lock:
            return all(not value for value in self.run_predecessors.values())

    async def update_run_state(self, *, run_predecessors, vertices_to_run) -> None:
        """Updates the run state with new predecessors and vertices to run."""
        async with self._lock:
            self.run_predecessors = run_predecessors
            self.vertices_to_run = vertices_to_run

    def update_run_state_sync(self, *, run_predecessors, vertices_to_run) -> None:
        """Synchronous version for graph setup/modification operations."""
        self.run_predecessors = run_predecessors
        self.vertices_to_run = vertices_to_run

    async def is_vertex_runnable(self, vertex_id: str, *, is_active: bool, is_loop: bool = False) -> bool:
        """Determines if a vertex is runnable based on its active state and predecessor fulfillment."""
        async with self._lock:
            if not is_active:
                return False
            if vertex_id in self.vertices_being_run:
                return False
            if vertex_id not in self.vertices_to_run:
                return False

            return await self._are_all_predecessors_fulfilled(vertex_id, is_loop=is_loop)

    def is_vertex_runnable_sync(self, vertex_id: str, *, is_active: bool, is_loop: bool = False) -> bool:
        """Synchronous wrapper for backward compatibility with tests."""
        if not is_active:
            return False
        if vertex_id in self.vertices_being_run:
            return False
        if vertex_id not in self.vertices_to_run:
            return False

        return self._are_all_predecessors_fulfilled_sync(vertex_id, is_loop=is_loop)

    def _are_all_predecessors_fulfilled_sync(self, vertex_id: str, *, is_loop: bool) -> bool:
        """Synchronous version for tests and graph setup."""
        if is_loop and vertex_id in self.ran_at_least_once:
            return True

        predecessors = self.run_predecessors.get(vertex_id, set())
        if not predecessors:
            return True

        return all(predecessor not in self.vertices_to_run for predecessor in predecessors)

    async def _are_all_predecessors_fulfilled(self, vertex_id: str, *, is_loop: bool) -> bool:
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
        pending: set[str] = self.run_predecessors.get(vertex_id, set())
        if not pending:
            return True

        if vertex_id in self.cycle_vertices:
            # If this is a loop vertex that has run before and has pending predecessors,
            # it should not run again to prevent infinite loops
            if is_loop and vertex_id in self.ran_at_least_once and pending:
                return False
            # Allow running if it's a loop or if none of its pending predecessors are cycle vertices
            return is_loop or pending.isdisjoint(self.cycle_vertices)

        return False

    async def remove_from_predecessors(self, vertex_id: str) -> None:
        """Removes a vertex from the predecessor list of its successors."""
        async with self._lock:
            predecessors = self.run_map.get(vertex_id, [])
            for predecessor in predecessors:
                if vertex_id in self.run_predecessors[predecessor]:
                    self.run_predecessors[predecessor].remove(vertex_id)

    async def _build_run_map(self, predecessor_map, vertices_to_run) -> None:
        """Builds a map of vertices and their runnable successors."""
        self.run_map = defaultdict(list)
        for vertex_id, predecessors in predecessor_map.items():
            for predecessor in predecessors:
                self.run_map[predecessor].append(vertex_id)
        # Convert predecessor_map values to sets for efficient membership and removals
        self.run_predecessors = defaultdict(set, {k: set(v) for k, v in predecessor_map.items()})
        self.vertices_to_run = vertices_to_run

    def build_run_map(self, predecessor_map, vertices_to_run) -> None:
        """Synchronous wrapper for building run map - used during initialization."""
        self.run_map = defaultdict(list)
        for vertex_id, predecessors in predecessor_map.items():
            for predecessor in predecessors:
                self.run_map[predecessor].append(vertex_id)
        # Convert predecessor_map values to sets for efficient membership and removals
        self.run_predecessors = defaultdict(set, {k: set(v) for k, v in predecessor_map.items()})
        self.vertices_to_run = vertices_to_run

    async def update_vertex_run_state(self, vertex_id: str, *, is_runnable: bool) -> None:
        """Updates the runnable state of a vertex."""
        async with self._lock:
            if is_runnable:
                self.vertices_to_run.add(vertex_id)
            else:
                self.vertices_being_run.discard(vertex_id)

    async def remove_vertex_from_runnables(self, v_id) -> None:
        await self.update_vertex_run_state(v_id, is_runnable=False)
        await self.remove_from_predecessors(v_id)

    def remove_from_predecessors_sync(self, vertex_id: str) -> None:
        """Synchronous version for use during graph setup/modification."""
        predecessors = self.run_map.get(vertex_id, [])
        for predecessor in predecessors:
            if vertex_id in self.run_predecessors[predecessor]:
                self.run_predecessors[predecessor].remove(vertex_id)

    def remove_vertex_from_runnables_sync(self, v_id) -> None:
        """Synchronous version for use during graph setup/modification."""
        self.vertices_being_run.discard(v_id)
        self.remove_from_predecessors_sync(v_id)

    async def add_to_vertices_being_run(self, v_id) -> None:
        async with self._lock:
            self.vertices_being_run.add(v_id)

    async def add_to_cycle_vertices(self, v_id):
        async with self._lock:
            self.cycle_vertices.add(v_id)
