const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  for (const [label, w, h] of [['desktop',1440,900], ['laptop',1280,800], ['tablet',834,1112], ['mobile',390,844]]) {
    const p = await (await b.newContext({viewport:{width:w,height:h}})).newPage();
    await p.goto('http://127.0.0.1:8899/', {waitUntil:'networkidle'});
    await p.waitForTimeout(700);
    const r = await p.evaluate(() => {
      const box = e => { if(!e) return null; const b = e.getBoundingClientRect(); return [Math.round(b.top), Math.round(b.bottom)]; };
      const svg = document.querySelectorAll('.landing-layer')[2];
      const txt = svg ? svg.querySelector('text') : null;
      const micro = [...document.querySelectorAll('#hero-content p')].pop();
      const btn = document.querySelector('#hero-content .landing-btn-primary');
      return {
        header: box(document.getElementById('site-header')),
        eyebrow: box(document.querySelector('.landing-eyebrow')),
        btn: box(btn),
        micro: box(micro),
        sign: txt ? box(txt) : null,
        signText: txt ? txt.textContent : null,
        heroH: Math.round(document.getElementById('hero').getBoundingClientRect().height),
      };
    });
    const overlap = (a,c) => a && c && a[1] > c[0] && a[0] < c[1];
    console.log(label.padEnd(8),
      'eyebrow', JSON.stringify(r.eyebrow),
      '| micro', JSON.stringify(r.micro),
      '| SIGN', JSON.stringify(r.sign),
      '| micro/sign overlap:', overlap(r.micro, r.sign),
      '| eyebrow/header overlap:', overlap(r.eyebrow, r.header));
    await p.context().close();
  }
  await b.close();
})();