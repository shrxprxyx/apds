"""
Brand Index Builder — Visual Service
Doc 4.3.2: Build FAISS index from real brand login page screenshots.

Steps:
1. Visits each brand login URL with Playwright
2. Screenshots the page
3. Runs EfficientNet-B3 to extract embeddings
4. Saves embeddings to FAISS index
5. Saves brand labels to JSON

Run: python build_brand_index.py
Output:
  models/visual/brand_index.faiss
  models/visual/brand_labels.json
"""

import asyncio
import json
from pathlib import Path

import numpy as np
import torch
import torchvision.transforms as transforms
from PIL import Image
import faiss
import io

# ─── Brand Login URLs ─────────────────────────────────────────
# Add/remove brands as needed. These are the real login pages.
BRAND_URLS = {
    "google": "https://accounts.google.com",
    "paypal": "https://www.paypal.com/signin",
    "facebook": "https://www.facebook.com/login",
    "apple": "https://appleid.apple.com",
    "microsoft": "https://login.microsoftonline.com",
    "amazon": "https://www.amazon.com/ap/signin",
    "netflix": "https://www.netflix.com/login",
    "instagram": "https://www.instagram.com/accounts/login",
    "twitter": "https://twitter.com/i/flow/login",
    "linkedin": "https://www.linkedin.com/login",
    "dropbox": "https://www.dropbox.com/login",
    "github": "https://github.com/login",
    "spotify": "https://accounts.spotify.com/en/login",
    "adobe": "https://auth.services.adobe.com",
    "yahoo": "https://login.yahoo.com",
    "chase": "https://secure.chase.com/web/auth/login",
    "wellsfargo": "https://connect.secure.wellsfargo.com/auth/login",
    "bankofamerica": "https://www.bankofamerica.com/online-banking/sign-in",
    "citibank": "https://online.citi.com/US/login.do",
    "dhl": "https://www.dhl.com/us-en/home/tracking.html",
    "fedex": "https://www.fedex.com/en-us/tracking.html",
    "ups": "https://www.ups.com/doapp/signin",
    "steam": "https://store.steampowered.com/login",
    "discord": "https://discord.com/login",
    "docusign": "https://account.docusign.com",
}

# ─── Paths ────────────────────────────────────────────────────
MODEL_OUT = Path("models/visual")
SCREENSHOT_DIR = Path("data/brand_screenshots")
BRAND_INDEX_PATH = MODEL_OUT / "brand_index.faiss"
BRAND_LABELS_PATH = MODEL_OUT / "brand_labels.json"
EMBEDDING_DIM = 1536    # EfficientNet-B3 feature dimension

MODEL_OUT.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Screenshot ───────────────────────────────────────────────
async def screenshot_brand(brand: str, url: str) -> bytes | None:
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page(
                viewport={"width": 1280, "height": 800}
            )
            try:
                await page.goto(url, timeout=10000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)  # wait for JS to render
                screenshot = await page.screenshot(type="png", full_page=False)
                # Save locally for inspection
                with open(SCREENSHOT_DIR / f"{brand}.png", "wb") as f:
                    f.write(screenshot)
                print(f"  ✓ {brand} — screenshot captured")
                return screenshot
            except Exception as e:
                print(f"  ✗ {brand} — failed: {e}")
                return None
            finally:
                await browser.close()
    except Exception as e:
        print(f"  ✗ {brand} — playwright error: {e}")
        return None


# ─── EfficientNet Embedding ───────────────────────────────────
def get_embedding(model, transform, image_bytes: bytes) -> np.ndarray | None:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = transform(img).unsqueeze(0)
        with torch.no_grad():
            embedding = model(tensor).squeeze().numpy()
        # L2 normalize for cosine similarity in FAISS
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        return embedding.astype(np.float32)
    except Exception as e:
        print(f"  ✗ embedding failed: {e}")
        return None


# ─── Load EfficientNet-B3 ─────────────────────────────────────
def load_efficientnet():
    import timm
    model = timm.create_model("efficientnet_b3", pretrained=True, num_classes=0)
    model.eval()

    transform = transforms.Compose([
        transforms.Resize((300, 300)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])
    return model, transform


# ─── Main ─────────────────────────────────────────────────────
async def main():
    print("Loading EfficientNet-B3...")
    model, transform = load_efficientnet()

    embeddings = []
    labels = []
    failed = []

    print(f"\nCapturing {len(BRAND_URLS)} brand screenshots...\n")

    for brand, url in BRAND_URLS.items():
        print(f"[{brand}] {url}")
        screenshot = await screenshot_brand(brand, url)

        if screenshot is None:
            failed.append(brand)
            continue

        embedding = get_embedding(model, transform, screenshot)
        if embedding is None:
            failed.append(brand)
            continue

        embeddings.append(embedding)
        labels.append(brand)

    if not embeddings:
        print("\nNo embeddings generated. Check your internet connection.")
        return

    # ── Build FAISS index ─────────────────────────────────────
    print(f"\nBuilding FAISS index with {len(embeddings)} brands...")
    embeddings_matrix = np.stack(embeddings)

    # Inner product index for cosine similarity (embeddings are L2 normalized)
    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(embeddings_matrix)

    faiss.write_index(index, str(BRAND_INDEX_PATH))
    print(f"FAISS index saved to {BRAND_INDEX_PATH}")

    with open(BRAND_LABELS_PATH, "w") as f:
        json.dump(labels, f, indent=2)
    print(f"Brand labels saved to {BRAND_LABELS_PATH}")

    if failed:
        print(f"\nFailed brands ({len(failed)}): {', '.join(failed)}")

    print(f"\nDone — {len(embeddings)} brands indexed successfully")
    print("Screenshots saved to data/brand_screenshots/ for inspection")


if __name__ == "__main__":
    asyncio.run(main())