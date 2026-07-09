import torch
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv

class GraphSAGEClassifier(torch.nn.Module):
    def __init__(self, in_channels: int, hidden: int = 64, out_channels: int = 1):
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden)
        self.conv2 = SAGEConv(hidden, hidden // 2)
        self.classifier = torch.nn.Linear(hidden // 2, out_channels)

    def forward(self, x, edge_index):
        x = F.relu(self.conv1(x, edge_index))
        x = F.dropout(x, p=0.3, training=self.training)
        x = F.relu(self.conv2(x, edge_index))
        # global mean pooling across all nodes → graph-level prediction
        x = x.mean(dim=0, keepdim=True)
        return torch.sigmoid(self.classifier(x))