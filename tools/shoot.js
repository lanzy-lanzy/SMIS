// Visual verification harness for the SMIS redesign.
// Usage: node tools/shoot.js [name=path ...] [--viewport]
// Captures the requested routes in light and dark, and reports console errors.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.env.SMIS_BASE || 'http://127.0.0.1:8899';
const OUT = path.join(__dirname, '..', 'tmp', 'shots');

const ROUTES = {
    dashboard: '/dashboard/',
    students: '/students/',
    academics: '/academics/',
    grades: '/grades/',
    submissions: '/grades/submissions/',
    form137: '/form137/',
    reports: '/reports/',
    users: '/accounts/users/',
    audit: '/accounts/audit-logs/',
    profile: '/accounts/profile/',
    change_password: '/accounts/change-password/',
    grade_levels: '/academics/grade-levels/',
    subjects: '/academics/subjects/',
    sections: '/academics/sections/',
    school_years: '/academics/school-years/',
    grading_periods: '/academics/grading-periods/',
    assignments: '/academics/assignments/',
    report_cards: '/reports/report-cards/',
    at_risk: '/reports/at-risk-students/',
    grade_trends: '/reports/grade-trends/',
};

// Pages that must be captured signed out.
const ANON = {
    login: '/accounts/login/',
    landing: '/',
};

(async () => {
    fs.mkdirSync(OUT, { recursive: true });

    const argv = process.argv.slice(2);
    const viewportOnly = argv.includes('--viewport');
    const args = argv.filter((a) => !a.startsWith('--'));
    const wanted = args.length
        ? args.map((a) => {
              const [name, url] = a.split('=');
              return { name, url: url || ROUTES[name] };
          })
        : Object.entries(ROUTES).map(([name, url]) => ({ name, url }));

    const browser = await chromium.launch();
    const problems = [];
    const shot = (page, name, theme) =>
        page.screenshot({
            path: path.join(OUT, `${name}-${theme}.png`),
            fullPage: !viewportOnly,
        });

    for (const theme of ['light', 'dark']) {
        const context = await browser.newContext({
            viewport: { width: 1440, height: 900 },
            deviceScaleFactor: 1,
        });
        const page = await context.newPage();

        page.on('console', (m) => {
            if (m.type() === 'error') problems.push(`[${theme}] console: ${m.text()}`);
        });
        page.on('pageerror', (e) => problems.push(`[${theme}] pageerror: ${e.message}`));

        // --- Signed-out captures -------------------------------------------
        for (const [name, url] of Object.entries(ANON)) {
            await page.goto(`${BASE}${url}`, { waitUntil: 'networkidle' });
            await page.evaluate((t) => {
                localStorage.setItem('darkMode', t === 'dark' ? 'true' : 'false');
            }, theme);
            await page.reload({ waitUntil: 'networkidle' });
            await page.waitForTimeout(600);
            await shot(page, name, theme);
        }

        // --- Sign in -------------------------------------------------------
        await page.goto(`${BASE}/accounts/login/`, { waitUntil: 'networkidle' });
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await Promise.all([
            page.waitForURL((u) => !u.pathname.includes('/accounts/login'), { timeout: 20000 }).catch(() => {}),
            page.click('button[type="submit"]'),
        ]);
        await page.waitForTimeout(1000);

        // --- Signed-in captures --------------------------------------------
        for (const { name, url } of wanted) {
            if (!url) continue;
            const bust = `${url}${url.includes('?') ? '&' : '?'}_=${Date.now()}`;
            try {
                await page.goto(`${BASE}${bust}`, { waitUntil: 'networkidle', timeout: 25000 });
            } catch (e) {
                problems.push(`[${theme}] ${name}: navigation failed ${e.message}`);
                continue;
            }
            await page.waitForTimeout(700);
            await shot(page, name, theme);
        }
        await context.close();
    }

    await browser.close();

    if (problems.length) {
        console.log('ISSUES:');
        [...new Set(problems)].forEach((p) => console.log('  - ' + p));
    } else {
        console.log('No console/page errors detected.');
    }
    console.log('Screenshots ->', OUT);
})();
