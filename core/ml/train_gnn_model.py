from pathlib import Path

import torch
from torch_geometric.data import Batch
from torch_geometric.loader import DataLoader
from torch_geometric.utils import to_undirected

from core.ml.gnn_dataset import load_gnn_dataset
from core.ml.gnn_model import GnnNodeClassifier


def train_gnn_model(
    graphml_dir: Path,
    feature_csv: Path,
    model_output_path: Path
):
    print("[DevArchAI] Loading GNN dataset...")
    data_list = load_gnn_dataset(graphml_dir, feature_csv)

    for data in data_list:
        data.edge_index = to_undirected(data.edge_index)

    loader = DataLoader(data_list, batch_size=2, shuffle=True)

    in_dim = data_list[0].num_node_features
    model = GnnNodeClassifier(in_dim=in_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005, weight_decay=1e-4)
    loss_fn = torch.nn.CrossEntropyLoss()

    model.train()
    for epoch in range(1, 61):
        total_loss = 0.0
        for batch in loader:
            optimizer.zero_grad()
            logits = model(batch.x, batch.edge_index)
            loss = loss_fn(logits, batch.y)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())

        if epoch % 10 == 0:
            print(f"[DevArchAI] Epoch {epoch} | Loss: {total_loss:.4f}")

    # Save model
    model_output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), model_output_path)
    print(f"[DevArchAI] GNN model saved to {model_output_path}")


if __name__ == "__main__":
    train_gnn_model(
        graphml_dir=Path("data/graphml"),
        feature_csv=Path("data/csv/structural_training_dataset.csv"),
        model_output_path=Path("data/models/devarchai_gnn_model.pt"),
    )
