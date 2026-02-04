from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import torch
import networkx as nx

from core.ml.gnn_model import GnnNodeClassifier
from core.ml.inference import DevArchAIInferenceEngine, generate_reason


class DevArchAIGnnInferenceEngine:
    """
    Loads a trained GNN model and performs node-level risk inference.
    """

    def __init__(self, model_path: Path):
        if not model_path.exists():
            raise FileNotFoundError(f"GNN model not found: {model_path}")

        self.feature_columns = DevArchAIInferenceEngine.MODEL_FEATURES
        self.model = GnnNodeClassifier(in_dim=len(self.feature_columns))
        self.model.load_state_dict(torch.load(model_path, map_location="cpu"))
        self.model.eval()

    def predict_service_risk(
        self,
        graph: nx.DiGraph,
        service_features: Dict[str, Dict[str, float]]
    ) -> List[Dict]:
        if not service_features:
            return []

        services = list(service_features.keys())
        node_idx = {s: i for i, s in enumerate(services)}

        # Build node features
        x_rows = []
        for service in services:
            feats = service_features.get(service, {})
            x_rows.append([float(feats.get(col, 0.0)) for col in self.feature_columns])

        x = torch.tensor(x_rows, dtype=torch.float32)

        # Build edges from graph
        edges = []
        for src, dst in graph.edges():
            if src in node_idx and dst in node_idx:
                edges.append([node_idx[src], node_idx[dst]])

        if edges:
            edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
        else:
            edge_index = torch.empty((2, 0), dtype=torch.long)

        with torch.no_grad():
            logits = self.model(x, edge_index)
            probs = torch.softmax(logits, dim=1)
            preds = torch.argmax(probs, dim=1)

        results = []
        for idx, service in enumerate(services):
            risk_level = int(preds[idx].item())
            confidence = float(probs[idx].max().item())
            results.append({
                "service": service,
                "predicted_risk_level": risk_level,
                "risk_confidence": confidence,
                "reason": generate_reason(
                    features=service_features[service],
                    risk_level=risk_level
                ),
                "model": "gnn"
            })

        results.sort(
            key=lambda x: (x["predicted_risk_level"], x["risk_confidence"]),
            reverse=True
        )

        return results
