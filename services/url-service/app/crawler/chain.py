import httpx
import dns.resolver
import tldextract
from dataclasses import dataclass, field

@dataclass
class ChainNode:
    url: str
    domain: str
    status_code: int | None
    hop_index: int
    is_final: bool

@dataclass  
class RedirectChain:
    nodes: list[ChainNode] = field(default_factory=list)
    edges: list[tuple[int, int]] = field(default_factory=list)  
    error: str | None = None

async def crawl_chain(url: str, max_hops: int = 10) -> RedirectChain:
    chain = RedirectChain()
    current_url = url

    async with httpx.AsyncClient(
        follow_redirects=False,   # manual redirect, we want each hop
        timeout=5.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; APDS-crawler/1.0)"},
        verify=False              
    ) as client:
        for hop in range(max_hops):
            try:
                resp = await client.get(current_url)
                extracted = tldextract.extract(current_url)
                domain = f"{extracted.domain}.{extracted.suffix}"

                node = ChainNode(
                    url=current_url,
                    domain=domain,
                    status_code=resp.status_code,
                    hop_index=hop,
                    is_final=resp.status_code not in (301, 302, 303, 307, 308)
                )
                chain.nodes.append(node)

                if hop > 0:
                    chain.edges.append((hop - 1, hop))

                if node.is_final:
                    break

                # follow the redirect manually
                location = resp.headers.get("location")
                if not location:
                    break
                current_url = location

            except Exception as e:
                chain.error = str(e)
                break

    return chain