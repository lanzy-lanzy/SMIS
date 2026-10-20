const { chromium } = require('playwright');
const path = require('path');
const OUT = path.join(__dirname, '..', 'tmp', 'shots');
(async () => {
  const b = await chromium.launch();
  for (const theme of ['light', 'dark']) {
    const ctx = await b.newContext({viewport:{width:1440,height:900}});
    const p = await ctx.newPage();
    await p.goto('http://127.0.0.1:8899/accounts/login/', {waitUntil:'networkidle'});
    await p.evaluate(t => localStorage.setItem('darkMode', t==='dark'?'true':'false'), theme);
    await p.reload({waitUntil:'networkidle'});
    await p.fill('input[name="username"]','admin');
    await p.fill('input[name="password"]','admin123');
    await Promise.all([p.waitForURL(u => !u.pathname.includes('login')).catch(()=>{}), p.click('button[type="submit"]')]);
    await p.waitForTimeout(1200);
    await p.goto('http://127.0.0.1:8899/students/', {waitUntil:'networkidle'});
    await p.waitForTimeout(600);
    // Open the "Add Student" modal
    await p.click('button:has-text("Add Student")');
    await p.waitForTimeout(1500);
    await p.screenshot({path: path.join(OUT, `modal-${theme}.png`)});
    await ctx.close();
  }
  await b.close();
  console.log('done');
})();