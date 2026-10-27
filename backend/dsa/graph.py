from collections import deque


# =========================================================
# GRAPH
# =========================================================

class SystemGraph:

    def __init__(self):
        self.adjacency_list = {}

    # -----------------------------------------------------
    # ADD VERTEX
    # -----------------------------------------------------

    def add_vertex(self, vertex):

        if vertex not in self.adjacency_list:
            self.adjacency_list[vertex] = []

    # -----------------------------------------------------
    # ADD EDGE
    # -----------------------------------------------------

    def add_edge(self, source, destination):

        self.add_vertex(source)
        self.add_vertex(destination)

        if destination not in self.adjacency_list[source]:

            self.adjacency_list[source].append(destination)

    # -----------------------------------------------------
    # DISPLAY GRAPH
    # -----------------------------------------------------

    def display(self):

        print("\nSNCS System Graph:")

        for vertex, neighbours in self.adjacency_list.items():

            print(
                f"{vertex} → "
                f"{', '.join(neighbours) if neighbours else 'None'}"
            )

    # -----------------------------------------------------
    # BFS
    # -----------------------------------------------------

    def bfs(self, start):

        if start not in self.adjacency_list:
            return []

        visited = set()

        queue = deque([start])

        traversal = []

        visited.add(start)

        while queue:

            current = queue.popleft()

            traversal.append(current)

            for neighbour in self.adjacency_list[current]:

                if neighbour not in visited:

                    visited.add(neighbour)

                    queue.append(neighbour)

        return traversal

    # -----------------------------------------------------
    # DFS
    # -----------------------------------------------------

    def dfs(self, start):

        if start not in self.adjacency_list:
            return []

        visited = set()

        traversal = []

        self._dfs_recursive(
            start,
            visited,
            traversal
        )

        return traversal

    def _dfs_recursive(
        self,
        vertex,
        visited,
        traversal
    ):

        visited.add(vertex)

        traversal.append(vertex)

        for neighbour in self.adjacency_list[vertex]:

            if neighbour not in visited:

                self._dfs_recursive(
                    neighbour,
                    visited,
                    traversal
                )

    # -----------------------------------------------------
    # CHECK CONNECTION
    # -----------------------------------------------------

    def has_connection(self, source, destination):

        return destination in self.bfs(source)


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    graph = SystemGraph()

    # -----------------------------------------------------
    # Add sensor connections
    # -----------------------------------------------------

    graph.add_edge("NTC", "PROCESSOR")

    graph.add_edge("DHT11", "PROCESSOR")

    graph.add_edge("ITG/MPU", "PROCESSOR")

    graph.add_edge("SW420", "PROCESSOR")

    # -----------------------------------------------------
    # Add actuator connections
    # -----------------------------------------------------

    graph.add_edge("PROCESSOR", "HEATER")

    graph.add_edge("PROCESSOR", "FAN")

    graph.add_edge("PROCESSOR", "BUZZER")

    # -----------------------------------------------------
    # Add dashboard connections
    # -----------------------------------------------------

    graph.add_edge("HEATER", "DASHBOARD")

    graph.add_edge("FAN", "DASHBOARD")

    graph.add_edge("BUZZER", "DASHBOARD")

    # -----------------------------------------------------
    # Display
    # -----------------------------------------------------

    graph.display()

    # -----------------------------------------------------
    # BFS
    # -----------------------------------------------------

    print("\nBFS Traversal from NTC:")

    bfs_result = graph.bfs("NTC")

    print(" → ".join(bfs_result))

    # -----------------------------------------------------
    # DFS
    # -----------------------------------------------------

    print("\nDFS Traversal from NTC:")

    dfs_result = graph.dfs("NTC")

    print(" → ".join(dfs_result))

    # -----------------------------------------------------
    # Connection tests
    # -----------------------------------------------------

    print("\nConnection Tests:")

    print(
        "NTC → HEATER:",
        graph.has_connection(
            "NTC",
            "HEATER"
        )
    )

    print(
        "NTC → DASHBOARD:",
        graph.has_connection(
            "NTC",
            "DASHBOARD"
        )
    )

    print(
        "ITG/MPU → DASHBOARD:",
        graph.has_connection(
            "ITG/MPU",
            "DASHBOARD"
        )
    )

    print(
        "SW420 → BUZZER:",
        graph.has_connection(
            "SW420",
            "BUZZER"
        )
    )

    print(
        "HX711 → PROCESSOR:",
        graph.has_connection(
            "HX711",
            "PROCESSOR"
        )
    )