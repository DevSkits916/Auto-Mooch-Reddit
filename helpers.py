import asyncio
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, expect

class AutomationError(RuntimeError):
    def __init__(self, code, message, *, security=False):
        super().__init__(f'{code}: {message}')
        self.code = code
        self.security = security

async def first_visible(page, locators, timeout_ms: int = 8000):
    if not isinstance(locators, list):
        locators = [locators]
    candidate = locators[0]
    for locator in locators[1:]:
        candidate = candidate.or_(locator)
    candidate = candidate.filter(visible=True).first
    try:
        await candidate.wait_for(state="visible", timeout=timeout_ms)
        return candidate
    except PlaywrightTimeoutError:
        return None


async def first_enabled(page, locators, timeout_ms: int = 8000):
    try:
        async with asyncio.timeout(timeout_ms / 1000):
            candidate = await first_visible(page, locators, timeout_ms)
            if candidate:
                await expect(candidate).to_be_enabled(timeout=timeout_ms)
                return candidate
    except (TimeoutError, AssertionError):
        pass
    return None
