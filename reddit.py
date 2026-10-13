"""Reddit text-post automation, CSV validation, and browser management."""
import csv
import io
import re
import asyncio
from urllib.parse import urlparse

from helpers import AutomationError, first_visible, first_enabled

ROOT = 'https://www.reddit.com'
OLD_ROOT = 'https://old.reddit.com'
COMMUNITY_PATTERN = re.compile(r'^[A-Za-z0-9_]{2,21}$')
RATE_WARNING = re.compile(r"doing that too much|you['’]ve been doing that a lot|try again in \d|take a break for|rate limit exceeded", re.I)


async def confirm_post(page, name):
    confirmed = asyncio.create_task(page.wait_for_url(re.compile(r'/r/' + re.escape(name) + r'/comments/[a-z0-9]+', re.I), timeout=20000))
    warning = page.get_by_text(RATE_WARNING).filter(visible=True).first
    limited = asyncio.create_task(warning.wait_for(state='visible', timeout=20000))
    try:
        done, _ = await asyncio.wait([confirmed, limited], return_when=asyncio.FIRST_COMPLETED)
        if await warning.is_visible():
            raise AutomationError('RATE_LIMIT', 'Reddit restricted posting. Worker stopped; wait before restarting.', security=True)
        if confirmed in done:
            await confirmed
        else:
            await limited
            raise AutomationError('RATE_LIMIT', 'Reddit restricted posting. Worker stopped.', security=True)
    finally:
        for task in (confirmed, limited):
            if not task.done():
                task.cancel()
        await asyncio.gather(confirmed, limited, return_exceptions=True)

def community_url(value):
    value = str(value or '').strip()
    if value.startswith(('r/', '/r/')):
        name = value.strip('/')[2:]
    else:
        parsed = urlparse(value)
        if parsed.scheme != 'https' or parsed.hostname not in ('reddit.com', 'www.reddit.com', 'old.reddit.com', 'new.reddit.com'):
            return None
        match = re.fullmatch(r'/r/([^/]+)/?', parsed.path)
        if not match:
            return None
        name = match[1]
    if not COMMUNITY_PATTERN.fullmatch(name) or name.lower() in ('all', 'popular', 'random', 'friends', 'mod'):
        return None
    return ROOT + '/r/' + name + '/'

def parse_reddit_csv(value):
    reader = csv.DictReader(io.StringIO(str(value or '').lstrip('\ufeff'), newline=''))
    headers = {str(h).strip().lower(): h for h in reader.fieldnames or []}
    def column(*names):
        return next((headers[name] for name in names if name in headers), None)
    url_column = column('url', 'community url', 'subreddit', 'subreddit_name', 'community name')
    title_column = column('title', 'post title')
    post_column = column('post', 'post text', 'post_text', 'body', 'message')
    name_column = column('community name', 'subreddit_name', 'subreddit', 'name')
    if not url_column or not title_column or not post_column:
        raise ValueError('Reddit CSV must include URL (or subreddit), title and post columns')
    valid, invalid = [], 0
    for record in reader:
        if not any(str(v or '').strip() for v in record.values()):
            continue
        raw_url = str(record.get(url_column) or '').strip()
        if not raw_url.startswith(('http', 'r/', '/r/')) and COMMUNITY_PATTERN.fullmatch(raw_url):
            raw_url = 'r/' + raw_url
        url = community_url(raw_url)
        title = str(record.get(title_column) or '').strip()
        post = str(record.get(post_column) or '').strip()
        if not url or not title or len(title) > 300 or not post or len(post) > 40000:
            invalid += 1
            continue
        valid.append(dict(groupName=str(record.get(name_column) or url.split('/')[4]).strip(), groupUrl=url,
                          title=title, postText=post, flair=str(record.get(column('flair')) or '').strip()))
    return valid, invalid

async def check_reddit_access(page, response=None):
    if response and response.status == 429:
        raise AutomationError('RATE_LIMIT', 'Reddit rate limited this request. Try later.', security=True)
    if response and response.status in (401, 403):
        raise AutomationError('ACCESS_BLOCKED', 'Reddit blocked access to this page.', security=True)
    body = await page.locator('body').inner_text(timeout=10000)
    if re.search(r'blocked by network security|whoa there|prove you.re human|verify you.re human|captcha', body, re.I):
        raise AutomationError('SECURITY_CHECK', 'Reddit requires a security check or blocked this network.', security=True)
    if re.search(r'/(?:login|account/login)(?:/|\?|$)', page.url) or await page.locator('input[type="password"]').count():
        raise AutomationError('LOGIN_REQUIRED', 'Log in to Reddit before starting.', security=True)
    if re.search(r'this community is private|this community has been banned|community not found|page not found', body, re.I):
        raise AutomationError('COMMUNITY_UNAVAILABLE', 'The community is private, banned or unavailable.')
    return body

async def apply_flair(page, flair):
    selector = await first_visible(page, [page.get_by_role('button', name=re.compile(r'flair', re.I)), page.locator('.flairselectbtn')], 1500)
    if not selector:
        raise AutomationError('FLAIR_UNAVAILABLE', 'CSV requests flair but Reddit did not expose a flair selector.')
    await selector.click()
    choice = await first_visible(page, [page.get_by_text(flair, exact=True)], 5000)
    if not choice:
        raise AutomationError('FLAIR_UNAVAILABLE', 'Requested flair was not available: ' + flair)
    await choice.click()
    apply = await first_visible(page, [page.get_by_role('button', name=re.compile(r'^(apply|save|select)$', re.I))], 2000)
    if apply:
        await apply.click()

async def post_to_reddit(page, job, on_step=lambda step: None, *, join_before_post=False, composer_timeout_ms=15000, **_options):
    url = community_url(job['groupUrl'])
    if not url or not job.get('title') or not job.get('postText'):
        raise AutomationError('INVALID_POST', 'Reddit requires a community URL, title and post text.')
    name = url.split('/')[4]
    submitted = False
    try:
        if join_before_post:
            on_step('Checking subreddit membership…')
            response = await page.goto(url, wait_until='domcontentloaded', timeout=45000)
            await check_reddit_access(page, response)
            join = await first_visible(page, [page.get_by_role('button', name=re.compile(r'^join$', re.I)), page.locator('.subscribe-button .add')], 5000)
            if join:
                on_step('Joining r/' + name + '…')
                await join.click(timeout=5000)
            else:
                on_step('No Join button found; attempting the composer anyway.')
        on_step('Opening r/' + name + ' text composer…')
        response = await page.goto((OLD_ROOT + '/r/' + name + '/submit?selftext=true') if job.get('legacy') else (url + 'submit'), wait_until='domcontentloaded', timeout=45000)
        await check_reddit_access(page, response)
        title = await first_visible(page, [page.locator('form#newlink textarea[name="title"]'), page.locator('form#newlink input[name="title"]')], min(4000, composer_timeout_ms)) if job.get('legacy') else None
        legacy = title is not None
        if not legacy:
            if job.get('legacy'):
                response = await page.goto(url + 'submit', wait_until='domcontentloaded', timeout=45000)
                await check_reddit_access(page, response)
            text_tab = await first_visible(page, [page.get_by_role('tab', name=re.compile(r'^(text|post)$', re.I))], 1500)
            if text_tab:
                await text_tab.click()
            title = await first_visible(page, [page.get_by_role('textbox', name=re.compile(r'^title', re.I)), page.locator('textarea[name="title"]'), page.get_by_placeholder(re.compile(r'^title', re.I))], composer_timeout_ms)
        if not title:
            raise AutomationError('COMPOSER_NOT_FOUND', 'Could not find the Reddit title field. Check login and community permissions.')
        on_step('Entering title and post text…')
        await title.fill(job['title'])
        editor = await first_visible(page, [page.locator('form#newlink textarea[name="text"]')] if legacy else [page.locator('[contenteditable="true"][role="textbox"]'), page.locator('[contenteditable="true"].tiptap'), page.get_by_role('textbox', name=re.compile(r'body|text \(optional\)', re.I))], composer_timeout_ms)
        if not editor:
            raise AutomationError('COMPOSER_NOT_FOUND', 'This community did not expose a supported text-post editor.')
        await editor.fill(job['postText'])
        actual_title = await title.input_value()
        actual_body = await editor.input_value() if await editor.evaluate('(e)=>e.tagName === "TEXTAREA" || e.tagName === "INPUT"') else await editor.inner_text()
        if actual_title != job['title'] or ' '.join(actual_body.split()) != ' '.join(job['postText'].split()):
            raise AutomationError('POST_TEXT_MISMATCH', 'Reddit composer did not match the CSV. Submission stopped.')
        if job.get('flair') or job.get('default_flair'):
            on_step('Selecting post flair…')
            await apply_flair(page, job.get('flair') or job['default_flair'])
        scope = page.locator('form#newlink') if legacy else page
        button = await first_enabled(page, [scope.get_by_role('button', name=re.compile(r'^(submit|post)$', re.I))], 4000)
        if not button:
            raise AutomationError('POST_BUTTON_UNAVAILABLE', 'Post button is unavailable. Community requirements may require flair or another post type.')
        on_step('Submitting post...')
        # Mark before the click: a navigation error can occur after Reddit accepted it.
        submitted = True
        await button.click()
        try:
            await confirm_post(page, name)
        except AutomationError:
            raise
        except Exception as error:
            body = await check_reddit_access(page)
            if re.search(r'doing that too much|try again in|take a break|rate limit', body, re.I):
                raise AutomationError('RATE_LIMIT', 'Reddit rejected the post with a rate limit. The run stopped.', security=True) from error
            errors = page.locator('.error:not(:empty), [role="alert"]')
            messages = [text.strip() for text in await errors.all_text_contents() if text.strip()]
            if messages:
                raise AutomationError('SUBMISSION_REJECTED', '; '.join(messages)[:500]) from error
            raise AutomationError('POST_UNCERTAIN', 'Submission clicked but no post URL was confirmed. Check Reddit before retrying.') from error
        on_step('Confirmed Reddit post URL: ' + page.url)
        return {'status': 'posted', 'postUrl': page.url}
    except AutomationError:
        raise
    except Exception as error:
        if submitted:
            raise AutomationError('POST_UNCERTAIN', 'Browser error after submission. Check Reddit before retrying.') from error
        raise
