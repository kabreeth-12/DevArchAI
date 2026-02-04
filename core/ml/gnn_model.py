from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv


class GnnNodeClassifier(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int = 64, out_dim: int = 3):
        super().__init__()
        self.gat1 = GATConv(in_dim, hidden_dim, heads=4, dropout=0.2)
        self.gat2 = GATConv(hidden_dim * 4, hidden_dim, heads=1, dropout=0.2)
        self.out = nn.Linear(hidden_dim, out_dim)

    def forward(self, x, edge_index):
        x = self.gat1(x, edge_index)
        x = F.elu(x)
        x = self.gat2(x, edge_index)
        x = F.elu(x)
        return self.out(x)
