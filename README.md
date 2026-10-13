# Auto Mooch Reddit

A separate Windows Python GUI with a Playwright worker for CSV-driven Reddit text posts. It uses a private persistent browser profile and never stores your password in source code.

## Windows downloads • no Python required

Download both apps from **[the latest release](https://github.com/DevSkits916/Auto-Mooch-Reddit/releases/latest)**:

- **AutoMoochReddit.exe:** imports your CSV, joins subreddits when enabled, and attempts text-post submission.
- **SubredditScanner.exe:** collects subreddit names and URLs and exports compatible CSVs.
- **SHA256SUMS.txt:** integrity checksums for both EXEs.

Double-click the app you want to run. Installed Microsoft Edge or Google Chrome is required. Each app has its own login profile; use **Open Login** once in each app, sign in, then press **Stop** to close the browser and save the session.

The poster stores private data in `%LOCALAPPDATA%\AutoMoochReddit`; the scanner uses `%LOCALAPPDATA%\AutoMoochRedditScanner`. Source installations use the local `data` folder. No credentials or private profiles are included in this repository or release. The EXEs are unsigned and Windows may display a publisher/SmartScreen warning.

You can also **[download the sample CSV](https://raw.githubusercontent.com/DevSkits916/Auto-Mooch-Reddit/main/sample%20CSV.csv)**. It uses placeholder communities—replace them with your own destinations and messages.

## Start

Requires Python 3.11 or later with Tkinter. Double-click `Start-Auto-Mooch-Reddit.bat`; it creates `.venv`, repairs missing pip, installs Playwright and Chromium, then opens the dashboard.

1. Click **Open Login**, sign in to Reddit, and press **Stop** to save the session and close the browser.
2. Prepare a CSV and click **Import CSV**.
3. Open **Show worker settings** to choose joining, headless mode, composer timeout, delay, optional default flair, or the old Reddit composer.
4. Click **Start Worker**. Joining and submission run automatically for each supported community.

Login, CAPTCHA, network blocks, private/restricted communities, moderator permissions, and account eligibility cannot be bypassed. The worker stops on security/rate limits and skips unavailable composers. It does not invent membership answers or automatically accept eligibility requirements.

## CSV format

### Separate subreddit scanner

Double-click `Start-Subreddit-Scanner.bat` in this same folder. This opens a separate app that collects community names and URLs from Reddit's community search pages.

1. Use **Open Login** if Reddit requires login. The scanner has its own browser profile, separate from the poster.
2. Enter search terms, one per line, and set the maximum results and search duration.
3. Click **Start Scan**. Results are deduplicated across searches and saved automatically. Stop retains collected results.
4. Enter your title and body for the exported posts. `{subreddit}` inserts the community name. Optional flair should match the communities you intend to post to.
5. Click **Export CSV**, then use **Import CSV** in Auto Mooch Reddit.

Export columns are exactly `name,url,title,post,flair`. Title and body must be filled so the poster accepts the exported CSV immediately. Review every destination and message before posting; search results do not imply permission to post or eligibility to join.

Scanning is limited to search results Reddit actually exposes; it is not an exhaustive directory. Network blocks, CAPTCHA and login restrictions are reported in the console and not bypassed. A failure screenshot is saved in `data/scanner/last-failure.png`, and results/logs/profile remain private under `data/scanner`. To test the scanner: `.\.venv\Scripts\python.exe -m unittest -v test_scanner`.

Required columns: `url,title,post`. Optional: `name,flair`. Header matching is case insensitive. `url` accepts a subreddit URL, `r/name`, or `/r/name`. Titles must be 1–300 characters and text 1–40000 characters. This version supports text posts, including links inside the body; it does not upload images/video or create polls.

`sample CSV.csv` contains two **placeholder test communities**, not recommended destinations. Replace the example names, URLs, titles and body text with your own before running. Add the exact community flair label if required; leave it blank otherwise. The CSV flair takes precedence over the default flair setting.

```csv
name,url,title,post,flair
My community,https://www.reddit.com/r/my_community/,My title,My text post,
```

The worker chooses only the flair you supply; it does not guess eligibility, approval or flair. Community rules remain your responsibility. Reddit may remove posts or hold them for moderation even after a post URL is confirmed.

## Controls

- **Headless:** run without a visible browser after signing in once.
- **Join subreddits automatically:** enable or disable Join clicks before posting. A missing Join button does not prevent a composer attempt.
- **Between groups:** interval between attempts; default 60 seconds, range 0–3600. A delay does not guarantee avoidance of platform limits.
- **Composer timeout:** field discovery timeout, default 15 seconds, range 1–300.
- **Default flair:** optional label used when the CSV row has none.
- **Use old Reddit text composer:** attempt the legacy form first, then the modern composer if no legacy form is found. Access restrictions are never bypassed.
- **Shuffle Pending:** reorder waiting communities before or during a run.
- **Skip Current Group:** cancel the current task; if submission started, mark it for review rather than retrying automatically.
- **Export Remaining CSV:** save waiting jobs in queue order with every original CSV column and multiline body retained.
- **Stop:** finish the current bounded task, then stop.

The whole window resizes. The right-side console has a draggable divider. Progress cards show complete, failed, skipped and remaining jobs. Settings apply when a run starts.

## Progress and restrictions

The worker confirms a Reddit `/comments/` post URL before marking Complete. This confirms submission, not visibility or moderator approval. Completed and uncertain posts are not automatically retried. Failed and skipped jobs may be retried on the next run. If a rate limit/network/security restriction is detected, the worker stops, sounds an alarm and leaves remaining jobs queued.

`data/` contains the login profile, saved progress, logs and diagnostic screenshots; keep it private. The Reddit app uses separate data from the Facebook app. Do not run multiple instances against this profile. Do not clear uncertain progress to retry without checking Reddit first.

## PowerShell setup and tests

From the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe -m unittest -v test_app
```

Optional Windows EXE build:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Build outputs are `releases/AutoMoochReddit.exe`, `releases/SubredditScanner.exe`, and `releases/SHA256SUMS.txt`.

English Reddit interfaces are currently supported. Local browser fixtures test posting mechanics; live authenticated Reddit posting remains unverified.

The live public-search check from the development environment was blocked by Reddit's security check. Scanner mechanics passed local browser tests, but a successful authenticated live scan has not been verified. The scanner reports blocks and retains collected results; it does not bypass them.
