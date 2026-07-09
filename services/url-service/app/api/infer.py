from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
import torch
from torch_geometric.data import Data

from app.crawler.chain import crawl_chain
from app.features.extractor import extract_features
from app.core.model import get_model

router = APIRouter(prefix="/infer")

class URLRequest(BaseModel):
    url: str
    context: str = "browser"

class URLResponse(BaseModel):
    score: float
    verdict: str
    hop_count: int
    chain_domains: list[str]
    signals: list[str]

@router.post("/url", response_model=URLResponse)
async def infer_url(req: URLRequest):
    # 1. crawl
    chain = await crawl_chain(req.url)
    if not chain.nodes:
        raise HTTPException(status_code=422, detail="Could not resolve URL")

    # 2. build graph tensors
    features = [extract_features(n.domain, n.hop_index, len(chain.nodes))
                for n in chain.nodes]
    x = torch.tensor(features, dtype=torch.float)

    if chain.edges:
        edge_index = torch.tensor(chain.edges, dtype=torch.long).t().contiguous()
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.long)

    # 3. GNN inference
    model = get_model()
    with torch.no_grad():
        score = model(x, edge_index).item()

    # 4. build human-readable signals
    signals = []
    if len(chain.nodes) > 3:
        signals.append(f"URL passed through {len(chain.nodes)} redirect hops")
    if chain.error:
        signals.append(f"Crawler error mid-chain: {chain.error}")
    final = chain.nodes[-1]
    if final.hop_index > 0:
        signals.append(f"Final destination: {final.domain}")

    verdict = "BLOCK" if score > 0.85 else "WARN" if score > 0.55 else "ALLOW"

    return URLResponse(
        score=round(score, 4),
        verdict=verdict,
        hop_count=len(chain.nodes),
        chain_domains=[n.domain for n in chain.nodes],
        signals=signals,
    )