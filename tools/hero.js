const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({viewport:{width:1440,height:900}})).newPage();
  await p.goto('http://127.0.0.1:8899/', {waitUntil:'networkidle'});
  await p.waitForTimeout(900);
  await p.screenshot({path: path.join(__dirname,'..','tmp','shots','landing-hero.png')});
  await b.close();
  console.log('done');
})();