import asyncio
import tempfile
import threading
import tkinter as tk
import unittest
from pathlib import Path
from playwright.async_api import async_playwright
from app import load_csv
from subreddit_scanner import Scanner, parse_links, export_csv, scan_query


class ScannerChecks(unittest.TestCase):
    def test_links_and_export_compatibility(self):
        rows = parse_links(['/r/python/', 'https://www.reddit.com/r/PYTHON/', '/r/dogs/', '/r/dogs/comments/xyz', '/user/example', 'https://evil.org/r/test/'])
        self.assertEqual(len(rows), 2)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'export.csv'
            export_csv(path, rows, 'Hello {subreddit}', 'Line one, quoted "text"\nLine two for {subreddit}')
            jobs = load_csv(path)
            self.assertEqual(len(jobs), 2)
            self.assertIn('r/dogs', jobs[1]['postText'])
            self.assertEqual(jobs[0]['source_headers'], ['name', 'url', 'title', 'post', 'flair'])
            with self.assertRaises(ValueError):
                export_csv(path, rows, '', '')

    def test_gui(self):
        root = tk.Tk()
        root.withdraw()
        try:
            scanner = Scanner(root)
            scanner.add(parse_links(['/r/python/', '/r/python/']))
            root.update()
            self.assertEqual(len(scanner.results), 1)
            self.assertEqual(root.resizable(), (1, 1))
        finally:
            root.destroy()

    def test_browser_collection(self):
        async def check():
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.route('https://www.reddit.com/search/**', lambda route: route.fulfill(body='<aside><a href="/r/sidebar/">Sidebar</a></aside><main><a href="/r/python/">Python</a><a href="/r/dogs/">Dogs</a><a href="/r/python/comments/x/">Post</a></main>', content_type='text/html'))
                    rows = []
                    count = await scan_query(page, 'dogs', 2, 10, threading.Event(), rows.extend, lambda _: None)
                    self.assertEqual(count, 2)
                    self.assertEqual(len(rows), 2)
                    self.assertFalse(any('sidebar' in row['url'] for row in rows))
                finally:
                    await browser.close()
        asyncio.run(check())


if __name__ == '__main__':
    unittest.main()
