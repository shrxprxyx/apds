import whois
import Levenshtein
import math
import tldextract
from datetime import datetime, timezone

# Top targeted brands for typosquatting check
BRANDS = ["paypal", "google", "apple", "microsoft", "amazon",
          "netflix", "facebook", "instagram", "chase", "wellsfargo",
          "bankofamerica", "citibank", "linkedin", "dropbox", "github"]

HIGH_RISK_TLDS = {"tk", "ml", "ga", "cf", "gq", "xyz", "top", "ru", "cn", "pw"}

def domain_entropy(domain: str) -> float:
    """Shannon entropy — random-looking domains score high."""
    if not domain:
        return 0.0
    freq = {c: domain.count(c) / len(domain) for c in set(domain)}
    return -sum(p * math.log2(p) for p in freq.values())

def typosquat_score(domain: str) -> float:
    """Min Levenshtein distance to any known brand, normalised 0-1."""
    name = tldextract.extract(domain).domain
    min_dist = min(Levenshtein.distance(name, brand) for brand in BRANDS)
    return max(0.0, 1.0 - min_dist / 10.0)

def tld_risk(domain: str) -> float:
    tld = tldextract.extract(domain).suffix.split(".")[-1]
    return 1.0 if tld in HIGH_RISK_TLDS else 0.0

def domain_age_days(domain: str) -> float:
    """Returns age in days. -1 if lookup fails."""
    try:
        w = whois.whois(domain)
        created = w.creation_date
        if isinstance(created, list):
            created = created[0]
        if created:
            age = (datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc)).days
            return float(age)
    except:
        pass
    return -1.0

def extract_features(domain: str, hop_index: int, chain_length: int) -> list[float]:
    """Returns a fixed-length feature vector for one node."""
    name = tldextract.extract(domain).domain
    return [
        float(len(domain)),             # domain length
        float(domain.count(".")),       # subdomain depth
        float(sum(c.isdigit() for c in domain)) / max(len(domain), 1),  # digit ratio
        domain_entropy(name),           # randomness
        typosquat_score(domain),        # brand similarity
        tld_risk(domain),               # risky TLD flag
        float(hop_index),               # position in chain
        float(chain_length),            # total chain length
        domain_age_days(domain),        # WHOIS age
    ]

FEATURE_DIM = 9  # must match the list above