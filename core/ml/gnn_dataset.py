from __future__ import annotations

from pathlib import Path
from typing import List, Dict

import pandas as pd
import torch
import networkx as nx
from torch_geometric.data import Data

from core.ml.inference import DevArchAIInferenceEngine


def _load_feature_table(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "service" not in df.columns or "risk_label" not in df.columns:
        raise ValueError("Dataset must include 'service' and 'risk_label' columns.")
    return df


def _node_features_for_service(
    row: pd.Series,
    feature_columns: List[str]
) -> List[float]:
    return [float(row.get(col, 0.0)) for col in feature_columns]


def build_graph_data(
    graphml_path: Path,
    feature_table: pd.DataFrame
) -> Data:
    graph = nx.read_graphml(graphml_path)
    if not isinstance(graph, nx.DiGraph):
        graph = nx.DiGraph(graph)

    project = graphml_path.stem
    services = list(graph.nodes())

    feature_columns = DevArchAIInferenceEngine.MODEL_FEATURES

    # Build node feature matrix and labels
    x_rows: List[List[float]] = []
    y_rows: List[int] = []

    for service in services:
        service_id = f"{project}::{service}"
        match = feature_table[feature_table["service"] == service_id]

        if match.empty:
            x_rows.append([0.0] * len(feature_columns))
            y_rows.append(0)
        else:
            row = match.iloc[0]
            x_rows.append(_node_features_for_service(row, feature_columns))
            y_rows.append(int(row["risk_label"]))

    x = torch.tensor(x_rows, dtype=torch.float32)
    y = torch.tensor(y_rows, dtype=torch.long)

    edge_index = []
    node_idx: Dict[str, int] = {s: i for i, s in enumerate(services)}

    for src, dst in graph.edges():
        if src in node_idx and dst in node_idx:
            edge_index.append([node_idx[src], node_idx[dst]])

    if edge_index:
        edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
    else:
        edge_index = torch.empty((2, 0), dtype=torch.long)

    data = Data(x=x, edge_index=edge_index, y=y)
    data.project = project
    return data


def load_gnn_dataset(
    graphml_dir: Path,
    feature_csv: Path
) -> List[Data]:
    feature_table = _load_feature_table(feature_csv)
    data_list: List[Data] = []

    for graphml_path in graphml_dir.glob("*.graphml"):
        data_list.append(build_graph_data(graphml_path, feature_table))

    if not data_list:
        raise ValueError("No GraphML files found for GNN dataset.")

    return data_list
