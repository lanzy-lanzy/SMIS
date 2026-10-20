const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({viewport:{width:1440,height:900}});
  const p = await ctx.newPage();
  const problems = [];
  p.on('console', m => { if (m.type()==='error') problems.push('console: '+m.text()); });
  p.on('pageerror', e => problems.push('pageerror: '+e.message));

  await p.goto('http://127.0.0.1:8899/accounts/login/', {waitUntil:'networkidle'});
  await p.fill('input[name="username"]','admin');
  await p.fill('input[name="password"]','admin123');
  await Promise.all([p.waitForURL(u => !u.pathname.includes('login')).catch(()=>{}), p.click('button[type="submit"]')]);
  await p.waitForTimeout(1200);

  // 1. HTMX filtered table swap on students
  await p.goto('http://127.0.0.1:8899/students/', {waitUntil:'networkidle'});
  await p.waitForTimeout(500);
  await p.selectOption('select[name="grade"]', { index: 1 }).catch(()=>{});
  await p.waitForTimeout(1200);
  console.log('filter swap ok:', await p.locator('#student-sections').count() > 0);

  // 2. View toggle (Alpine segmented control)
  await p.click('button:has-text("Table")');
  await p.waitForTimeout(500);
  console.log('table view visible:', await p.locator('#student-table').isVisible());

  // 3. Modal round-trip
  await p.click('button:has-text("Add Student")');
  await p.waitForTimeout(1500);
  console.log('modal open:', await p.locator('#modal-content input').count() > 0);
  await p.keyboard.press('Escape');
  await p.waitForTimeout(600);
  console.log('modal closed:', (await p.locator('#modal-content input').count()) === 0);

  // 4. Account dropdown
  await p.click('button[aria-label="Open account menu"]');
  await p.waitForTimeout(500);
  console.log('account menu visible:', await p.locator('text=Change password').isVisible());

  // 5. Theme toggle
  await p.click('button[aria-label="Toggle color theme"]');
  await p.waitForTimeout(500);
  console.log('dark toggled:', await p.evaluate(() => document.documentElement.classList.contains('dark')));

  // 6. Academics list -> open edit modal
  await p.goto('http://127.0.0.1:8899/academics/grade-levels/', {waitUntil:'networkidle'});
  await p.click('button:has-text("Edit")');
  await p.waitForTimeout(1200);
  console.log('edit modal:', await p.locator('#modal-content input').count() > 0);

  // 7. Pagination on academic table
  await p.goto('http://127.0.0.1:8899/academics/sections/', {waitUntil:'networkidle'});
  await p.waitForTimeout(400);
  const pageLinks = await p.locator('a.page-link').count();
  console.log('pagination links:', pageLinks);

  // 8. Grades page segmented
  await p.goto('http://127.0.0.1:8899/grades/', {waitUntil:'networkidle'});
  await p.waitForTimeout(600);
  console.log('grades cards:', await p.locator('.glass-card').count());

  await b.close();
  console.log(problems.length ? 'PROBLEMS:\n' + [...new Set(problems)].join('\n') : 'No console errors.');
})();