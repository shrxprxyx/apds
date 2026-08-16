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
    name = tldextract.extract(domain).domain
    
    # raw values
    domain_len    = len(domain)
    dot_count     = domain.count(".")
    digit_ratio   = sum(c.isdigit() for c in domain) / max(len(domain), 1)
    entropy       = domain_entropy(name)
    typosquat     = typosquat_score(domain)
    tld_risk_val  = tld_risk(domain)
    age_days      = domain_age_days(domain)

    # normalise each feature into roughly [0, 1]
    domain_len_norm  = min(domain_len / 100.0, 1.0)       # cap at 100 chars
    dot_count_norm   = min(dot_count / 5.0, 1.0)          # cap at 5 dots
    hop_norm         = min(hop_index / 10.0, 1.0)         # cap at 10 hops
    chain_norm       = min(chain_length / 10.0, 1.0)      # cap at 10 hops
    
    # age: -1 (unknown) → 0.5 (uncertain), 0 days → 1.0 (very suspicious), 3650+ days → 0.0 (very old = safe)
    if age_days < 0:
        age_norm = 0.5
    else:
        age_norm = max(0.0, 1.0 - (age_days / 3650.0))   # 10 years = fully safe

    return [
        domain_len_norm,   # 0-1
        dot_count_norm,    # 0-1
        digit_ratio,       # already 0-1
        min(entropy / 5.0, 1.0),  # entropy max ~5 bits for short strings
        typosquat,         # already 0-1
        tld_risk_val,      # already 0 or 1
        hop_norm,          # 0-1
        chain_norm,        # 0-1
        age_norm,          # 0-1
    ]
    
FEATURE_DIM = 9  # must match the list above