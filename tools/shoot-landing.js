// Full-page capture of the public landing page (signed out).
const { chromium } = require('playwright');
const path = require('path');

const BASE = process.env.SMIS_BASE || 'http://127.0.0.1:8899';
const OUT = path.join(__dirname, '..', 'tmp', 'shots');

(async () => {
    const browser = await chromium.launch();
    for (const theme of ['light', 'dark']) {
        const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
        const page = await context.newPage();
        await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
        await page.evaluate((t) => localStorage.setItem('darkMode', t === 'dark' ? 'true' : 'false'), theme);
        await page.reload({ waitUntil: 'networkidle' });
        // Trigger every scroll-linked reveal before capturing. The observer
        // needs a beat per step, so step slowly enough for it to fire.
        await page.evaluate(async () => {
            const step = window.innerHeight * 0.5;
            for (let y = 0; y < document.body.scrollHeight; y += step) {
                window.scrollTo(0, y);
                await new Promise((r) => setTimeout(r, 350));
            }
            window.scrollTo(0, 0);
        });
        await page.waitForTimeout(1200);
        await page.screenshot({ path: path.join(OUT, `landing-full-${theme}.png`), fullPage: true });
        await context.close();
    }
    await browser.close();
    console.log('done');
})();
