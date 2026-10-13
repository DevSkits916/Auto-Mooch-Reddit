import asyncio
import csv
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from playwright.async_api import async_playwright
from app import App, load_csv
from reddit import community_url, post_to_reddit, check_reddit_access, confirm_post
from helpers import AutomationError


class Checks(unittest.TestCase):
    def test_csv(self):
        jobs = load_csv(Path(__file__).parent / 'sample CSV.csv')
        self.assertEqual(len(jobs), 2)
        self.assertIn('\n', jobs[1]['postText'])
        self.assertEqual(community_url('r/python'), 'https://www.reddit.com/r/python/')
        for value in ['https://reddit.com.evil.com/r/python', 'http://reddit.com/r/python', 'https://reddit.com/r/python/comments/x', 'r/all']:
            self.assertIsNone(community_url(value))
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'bad.csv'
            file.write_text('url,post\nr/python,Hello\n')
            with self.assertRaises(ValueError):
                load_csv(file)

    def test_gui_export_and_resize(self):
        root = tk.Tk()
        try:
            app = App(root)
            app.jobs = load_csv(Path(__file__).parent / 'sample CSV.csv')
            for i, job in enumerate(app.jobs):
                app.table.insert('', 'end', iid=str(i), values=(job['name'], 'Queued'))
            root.geometry('900x600')
            root.update()
            self.assertGreater(app.table.winfo_height(), 50)
            app.toggle_settings()
            root.update()
            self.assertGreater(app.table.winfo_height(), 40)
            self.assertEqual(root.title(), 'Auto Mooch Reddit')
            app.table.move('1', '', 0)
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / 'remaining.csv'
                with patch('app.filedialog.asksaveasfilename', return_value=str(output)), patch('app.messagebox.showinfo'):
                    app.export_remaining()
                exported = load_csv(output)
                self.assertEqual(exported[0]['source_row'], app.jobs[1]['source_row'])
        finally:
            root.destroy()

    def test_modern_join_and_post(self):
        asyncio.run(self.browser_post(False))

    def test_legacy_post(self):
        asyncio.run(self.browser_post(True))

    async def browser_post(self, legacy):
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                events = []
                async def route_handler(route):
                    url = route.request.url
                    if '/comments/' in url:
                        html = '<h1>Fixture confirmed post</h1>'
                    elif '/submit' in url:
                        if legacy:
                            html = '<form id="newlink"><textarea name="title"></textarea><textarea name="text"></textarea><button type="button" onclick="location.href=\'/r/testsub/comments/abc123/fixture\'">submit</button></form>'
                        else:
                            html = '<textarea aria-label="Title"></textarea><div contenteditable="true" role="textbox" aria-label="Body"></div><button onclick="location.href=\'/r/testsub/comments/abc123/fixture\'">Post</button>'
                    else:
                        html = '<button onclick="this.textContent=\'Joined\'">Join</button>'
                    await route.fulfill(body=html, content_type='text/html')
                await page.route('https://**reddit.com/**', route_handler)
                result = await post_to_reddit(page, dict(groupUrl='https://www.reddit.com/r/testsub/', title='Fixture title', postText='Fixture body\nsecond line', legacy=legacy), events.append, join_before_post=not legacy, composer_timeout_ms=2000)
                self.assertEqual(result['status'], 'posted')
                self.assertIn('/comments/abc123', result['postUrl'])
                self.assertIn('Submitting post...', events)
                if not legacy:
                    self.assertTrue(any('Joining r/' in event for event in events))
            finally:
                await browser.close()

    def test_security_detection(self):
        async def check():
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.set_content('<h1>You have been blocked by network security</h1>')
                    with self.assertRaises(AutomationError) as raised:
                        await check_reddit_access(page)
                    self.assertTrue(raised.exception.security)
                finally:
                    await browser.close()
        asyncio.run(check())

    def test_rate_warning(self):
        async def check():
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.set_content('<div id="error"></div><script>setTimeout(()=>document.querySelector("#error").textContent="Looks like you have been doing that too much. Try again in 10 minutes.",100)</script>')
                    with self.assertRaises(AutomationError) as raised:
                        await confirm_post(page, 'testsub')
                    self.assertEqual(raised.exception.code, 'RATE_LIMIT')
                    self.assertTrue(raised.exception.security)
                finally:
                    await browser.close()
        asyncio.run(check())

    def test_worker_stops_before_next_community(self):
        async def check():
            root = tk.Tk()
            root.withdraw()
            try:
                app = App(root)
                app.jobs = load_csv(Path(__file__).parent / 'sample CSV.csv')
                app.pending = [0, 1]
                app.history = {}
                page = Mock()
                page.screenshot = AsyncMock()
                context = Mock(pages=[page])
                context.close = AsyncMock()
                pw = Mock()
                pw.chromium.launch_persistent_context = AsyncMock(return_value=context)
                manager = Mock()
                manager.__aenter__ = AsyncMock(return_value=pw)
                manager.__aexit__ = AsyncMock(return_value=None)
                worker = AsyncMock(side_effect=AutomationError('RATE_LIMIT', 'Posting limit', security=True))
                with tempfile.TemporaryDirectory() as folder:
                    app.history_path = Path(folder) / 'progress.json'
                    with patch('app.async_playwright', return_value=manager), patch('app.post_to_reddit', new=worker):
                        await app.run(False, True, 0, [])
                self.assertEqual(worker.await_count, 1)
                self.assertEqual(app.pending, [1])
                self.assertTrue(app.stop.is_set())
                self.assertTrue(any(event[0] == 'alert' for event in list(app.events.queue)))
            finally:
                root.destroy()
        asyncio.run(check())


if __name__ == '__main__':
    unittest.main()
