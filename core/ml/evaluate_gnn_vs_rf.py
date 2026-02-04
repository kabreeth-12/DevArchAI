from pathlib import Path

import numpy as np
import torch
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from core.ml.gnn_dataset import load_gnn_dataset
from core.ml.gnn_model import GnnNodeClassifier
from core.ml.inference import DevArchAIInferenceEngine


def evaluate():
    graphml_dir = Path("data/graphml")
    feature_csv = Path("data/csv/structural_training_dataset.csv")
    gnn_model_path = Path("data/models/devarchai_gnn_model.pt")

    # Load GNN dataset
    data_list = load_gnn_dataset(graphml_dir, feature_csv)

    # Load trained GNN
    gnn_model = GnnNodeClassifier(
        in_dim=len(DevArchAIInferenceEngine.MODEL_FEATURES)
    )
    gnn_model.load_state_dict(torch.load(gnn_model_path, map_location="cpu"))
    gnn_model.eval()

    rf_preds = []
    gnn_preds = []
    y_true = []

    for data in data_list:
        X = data.x.numpy()
        y = data.y.numpy()

        # Train Random Forest INLINE to ensure feature compatibility
        rf_model = Pipeline([
            ("scaler", StandardScaler()),
            ("rf", RandomForestClassifier(
                n_estimators=100,
                random_state=42
            ))
        ])

        rf_model.fit(X, y)
        rf_pred = rf_model.predict(X)

        # GNN inference
        with torch.no_grad():
            logits = gnn_model(data.x, data.edge_index)
            gnn_pred = torch.argmax(logits, dim=1).numpy()

        rf_preds.append(rf_pred)
        gnn_preds.append(gnn_pred)
        y_true.append(y)

    rf_preds = np.concatenate(rf_preds)
    gnn_preds = np.concatenate(gnn_preds)
    y_true = np.concatenate(y_true)

    print("[DevArchAI] Evaluation on available graphs")
    print(f"RF Accuracy: {accuracy_score(y_true, rf_preds):.4f}")
    print(f"RF Macro F1: {f1_score(y_true, rf_preds, average='macro'):.4f}")
    print(f"GNN Accuracy: {accuracy_score(y_true, gnn_preds):.4f}")
    print(f"GNN Macro F1: {f1_score(y_true, gnn_preds, average='macro'):.4f}")


if __name__ == "__main__":
    evaluate()
