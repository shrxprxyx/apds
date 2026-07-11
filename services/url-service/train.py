import asyncio
import csv
import random
import torch
from pathlib import Path
from torch_geometric.data import Data
from torch.optim import Adam
import torch.nn.functional as F

from app.crawler.chain import crawl_chain
from app.features.extractor import extract_features
from app.gnn.graphsage import GraphSAGEClassifier, FEATURE_DIM  # add FEATURE_DIM to graphsage.py

# ── paths ──────────────────────────────────────────────────────────────────
PHISH_FILE   = Path("data/raw/openphish.txt")
LEGIT_FILE   = Path("data/raw/tranco.csv")
SAVE_PATH    = Path("models/graphsage.pt")
SAVE_PATH.parent.mkdir(exist_ok=True)

# ── config ─────────────────────────────────────────────────────────────────
MAX_PHISH    = 200   # how many phishing URLs to crawl
MAX_LEGIT    = 200   # how many legit domains to crawl
EPOCHS       = 30
LR           = 0.01

# ───────────────────────────────────────────────────────────────────────────

def load_phishing_urls(n: int) -> list[str]:
    urls = []
    with open(PHISH_FILE) as f:
        for line in f:
            url = line.strip()
            if url and url.startswith("http"):
                urls.append(url)
            if len(urls) >= n:
                break
    print(f"  loaded {len(urls)} phishing URLs")
    return urls

def load_legit_urls(n: int) -> list[str]:
    domains = []
    with open(LEGIT_FILE) as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                domain = row[1].strip()
                domains.append(f"https://{domain}")
            if len(domains) >= n:
                break
    print(f"  loaded {len(domains)} legit domains")
    return domains

async def url_to_graph(url: str, label: int) -> Data | None:
    """Crawl one URL and turn its redirect chain into a PyG Data object."""
    try:
        chain = await crawl_chain(url)
        if not chain.nodes:
            return None

        features = [
            extract_features(n.domain, n.hop_index, len(chain.nodes))
            for n in chain.nodes
        ]
        x = torch.tensor(features, dtype=torch.float)

        if chain.edges:
            edge_index = torch.tensor(
                chain.edges, dtype=torch.long
            ).t().contiguous()
        else:
            # single node — no edges
            edge_index = torch.zeros((2, 0), dtype=torch.long)

        y = torch.tensor([label], dtype=torch.float)
        return Data(x=x, edge_index=edge_index, y=y)

    except Exception as e:
        print(f"    skip {url[:60]} — {e}")
        return None

async def build_dataset(phish_urls: list, legit_urls: list) -> list[Data]:
    dataset = []

    print("\n[1/2] crawling phishing URLs...")
    for i, url in enumerate(phish_urls):
        print(f"  [{i+1}/{len(phish_urls)}] {url[:70]}")
        graph = await url_to_graph(url, label=1)
        if graph:
            dataset.append(graph)
        await asyncio.sleep(0.1)  # be polite, don't hammer servers

    print(f"\n[2/2] crawling legit domains...")
    for i, url in enumerate(legit_urls):
        print(f"  [{i+1}/{len(legit_urls)}] {url[:70]}")
        graph = await url_to_graph(url, label=0)
        if graph:
            dataset.append(graph)
        await asyncio.sleep(0.1)

    random.shuffle(dataset)
    print(f"\n  dataset size: {len(dataset)} graphs")
    print(f"  phishing: {sum(1 for d in dataset if d.y.item() == 1)}")
    print(f"  legit:    {sum(1 for d in dataset if d.y.item() == 0)}")
    return dataset

def train(dataset: list[Data]):
    from app.gnn.graphsage import FEATURE_DIM
    
    # split 80/20
    split = int(0.8 * len(dataset))
    train_set = dataset[:split]
    val_set   = dataset[split:]

    model = GraphSAGEClassifier(in_channels=FEATURE_DIM)
    optimizer = Adam(model.parameters(), lr=LR)

    print(f"\ntraining on {len(train_set)} graphs, validating on {len(val_set)}...")

    for epoch in range(1, EPOCHS + 1):
        # ── train ──
        model.train()
        total_loss = 0
        for data in train_set:
            optimizer.zero_grad()
            out = model(data.x, data.edge_index)
            loss = F.binary_cross_entropy(out, data.y.unsqueeze(0))
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        # ── validate ──
        model.eval()
        correct = 0
        with torch.no_grad():
            for data in val_set:
                score = model(data.x, data.edge_index).item()
                pred  = 1 if score > 0.5 else 0
                if pred == int(data.y.item()):
                    correct += 1

        acc = correct / len(val_set) if val_set else 0
        avg_loss = total_loss / len(train_set)

        if epoch % 5 == 0 or epoch == 1:
            print(f"  epoch {epoch:02d}/{EPOCHS} | loss: {avg_loss:.4f} | val acc: {acc:.2%}")

    # ── save ──
    torch.save(model.state_dict(), SAVE_PATH)
    print(f"\nmodel saved to {SAVE_PATH}")
    return model

async def main():
    print("=== APDS GNN Training ===\n")

    print("loading URLs...")
    phish = load_phishing_urls(MAX_PHISH)
    legit  = load_legit_urls(MAX_LEGIT)

    dataset = await build_dataset(phish, legit)

    if len(dataset) < 10:
        print("ERROR: too few samples crawled. Check your internet connection.")
        return

    train(dataset)
    print("\ndone. restart url-service and scores will now be real.")

if __name__ == "__main__":
    asyncio.run(main())