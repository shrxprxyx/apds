import io
import hashlib
import structlog
from typing import Optional

from app.core.config import settings

logger = structlog.get_logger()


async def capture_screenshot(url: str) -> Optional[bytes]:
    """
    Doc 4.3.1: Playwright headless Chromium screenshot capture.
    Timeout: 2000ms per doc.
    Resolution: 1280x800.
    Returns raw PNG bytes or None if capture fails.
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            page = await browser.new_page(
                viewport={
                    "width": settings.SCREENSHOT_WIDTH,
                    "height": settings.SCREENSHOT_HEIGHT,
                }
            )

            try:
                await page.goto(
                    url,
                    timeout=settings.SCREENSHOT_TIMEOUT_MS,
                    wait_until="domcontentloaded",
                )
                screenshot_bytes = await page.screenshot(
                    type="png",
                    full_page=False,
                )
                logger.info("screenshot captured", url=url)
                return screenshot_bytes

            except Exception as e:
                logger.warning("screenshot failed", url=url, error=str(e))
                return None

            finally:
                await browser.close()

    except Exception as e:
        logger.error("playwright error", error=str(e))
        return None


async def upload_screenshot_to_minio(
    screenshot_bytes: bytes,
    url: str,
) -> Optional[str]:
    """
    Upload screenshot PNG to MinIO apds-screenshots bucket.
    Returns the MinIO object key.
    Doc 7.3: screenshots stored in MinIO apds-screenshots bucket.
    """
    try:
        from minio import Minio

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
        )

        # Use url hash as object key for dedup
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        object_key = f"screenshots/{url_hash}.png"

        # Ensure bucket exists
        if not client.bucket_exists(settings.MINIO_BUCKET_SCREENSHOTS):
            client.make_bucket(settings.MINIO_BUCKET_SCREENSHOTS)

        client.put_object(
            settings.MINIO_BUCKET_SCREENSHOTS,
            object_key,
            io.BytesIO(screenshot_bytes),
            length=len(screenshot_bytes),
            content_type="image/png",
        )

        logger.info("screenshot uploaded", object_key=object_key)
        return object_key

    except Exception as e:
        logger.error("minio upload failed", error=str(e))
        return None