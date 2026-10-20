'use strict';
// Synthetic workspace only; all browser traffic is restricted to loopback.
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.SME_AUDIT_PLAYWRIGHT);

(async () => {
  const base = process.env.SME_AUDIT_BASE_URL;
  const directory = process.env.SME_AUDIT_WORKSPACE;
  if (!base || new URL(base).hostname !== '127.0.0.1' || !directory) throw new Error('isolated workspace required');
  const out = 'artifacts/submission-audit-20261019';
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const result = {scope: 'Fresh Edge smoke, synthetic MOCK, no payment approvals', browser: browser.version(), pages: [], errors: [], checks: {}};
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin ? route.continue() : route.abort());
    const page = await context.newPage();
    page.on('pageerror', e => result.errors.push(e.message));
    await page.goto(base);
    await page.locator('#token').fill(JSON.parse(fs.readFileSync(path.join(directory,'local-login.secret.json'),'utf8')).OWNER);
    await page.getByRole('button', {name: 'Sign in', exact: true}).click();
    await page.locator('#app').waitFor({state: 'visible'});
    await page.waitForFunction(() => document.querySelector('#main h1') && document.querySelector('#main').getAttribute('aria-busy') === 'false');
    result.checks.chinese_company_visible = (await page.locator('#company').innerText()).includes('苏州');
    result.checks.model_mock_label = (await page.locator('#model-badge').innerText()) === 'MODEL MOCK';
    result.checks.no_browser_token_storage = await page.evaluate(() => localStorage.length === 0 && sessionStorage.length === 0 && document.querySelector('#token').value === '');
    for (const width of [1440, 768, 390]) {
      await page.setViewportSize({width, height: 1000});
      for (const route of ['home','money','case','documents','activity','settings']) {
        await page.goto(base + '/#' + route);
        await page.waitForFunction(() => document.querySelector('#main h1') && document.querySelector('#main').getAttribute('aria-busy') === 'false');
        const state = await page.evaluate(() => ({title: document.querySelector('#main h1').textContent, overflow: document.documentElement.scrollWidth > innerWidth, failed: document.querySelector('#main').textContent.includes('Could not load this page')}));
        result.pages.push({width, route, ...state});
        if (['home','money'].includes(route)) await page.screenshot({path: `${out}/ui-${route}-${width}.png`, fullPage: true});
      }
    }
    await page.reload();
    await page.locator('#app').waitFor({state: 'visible'});
    result.checks.session_survives_reload = await page.locator('#login').isHidden();
    result.checks.no_page_errors = result.errors.length === 0;
    result.checks.no_page_overflow = result.pages.every(p => !p.overflow);
    result.checks.routes_render = result.pages.every(p => p.title && !p.failed);
    result.passed = Object.values(result.checks).every(Boolean);
    fs.writeFileSync(`${out}/browser-smoke.json`, JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(e => { console.error(e.message); process.exitCode = 1; });
