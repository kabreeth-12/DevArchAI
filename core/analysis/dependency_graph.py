import networkx as nx
from typing import List, Tuple


class ServiceDependencyGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_services(self, services: List[str]):
        for service in services:
            self.graph.add_node(service)

    def add_dependency(self, source: str, target: str):
        if source != target:
            self.graph.add_edge(source, target)

    def get_edges(self) -> List[Tuple[str, str]]:
        return list(self.graph.edges())

    def get_nodes(self) -> List[str]:
        return list(self.graph.nodes())
