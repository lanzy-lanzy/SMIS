const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({viewport:{width:1440,height:900}});
  const p = await ctx.newPage();
  const problems = [];
  p.on('pageerror', e => problems.push('pageerror: '+e.message));
  p.on('console', m => { if (m.type()==='error') problems.push('console: '+m.text()); });
  await p.goto('http://127.0.0.1:8899/accounts/login/', {waitUntil:'networkidle'});
  await p.fill('input[name="username"]','student1');
  await p.fill('input[name="password"]','student123');
  await Promise.all([p.waitForURL(u => !u.pathname.includes('login')).catch(()=>{}), p.click('button[type="submit"]')]);
  await p.waitForTimeout(1500);
  console.log('student redirected to:', new URL(p.url()).pathname);
  await p.screenshot({path: path.join(__dirname,'..','tmp','shots','student-role.png')});
  await b.close();
  console.log(problems.length ? 'PROBLEMS: '+[...new Set(problems)].join(' | ') : 'No errors.');
})();