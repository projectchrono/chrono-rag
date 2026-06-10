const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 800 });

  // Step 1: Initial load
  await page.goto('http://localhost:5173/');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: '/tmp/initial.png' });
  const title = await page.title();
  const h1 = await page.textContent('h1');
  const subtitle = await page.textContent('p');
  console.log('title:', title);
  console.log('h1:', h1);
  console.log('subtitle:', subtitle);
  const input = await page.$('input[type="text"]');
  const button = await page.$('button');
  console.log('has input:', !!input);
  console.log('button disabled on empty:', await button.evaluate(b => b.disabled));

  // Check background color
  const bodyBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  console.log('body background:', bodyBg);

  // Step 2: Type a query - button should enable
  await page.fill('input[type="text"]', 'What is Chrono?');
  const buttonEnabled = await button.evaluate(b => !b.disabled);
  console.log('button enabled after typing:', buttonEnabled);
  await page.screenshot({ path: '/tmp/typed.png' });

  // Step 3: Submit - will fail (no backend), should show error
  await page.click('button');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: '/tmp/after-submit.png' });
  const errorText = await page.textContent('[role="alert"]').catch(() => null);
  console.log('error message:', errorText);
  
  // Check layout compact mode
  const pageClass = await page.$eval('[class*="page"]', el => el.className);
  console.log('page class after submit:', pageClass);

  // Step 4: Probe - empty query, button should be disabled
  await page.fill('input[type="text"]', '');
  await page.screenshot({ path: '/tmp/empty-query.png' });
  const buttonDisabledAgain = await button.evaluate(b => b.disabled);
  console.log('button disabled on empty again:', buttonDisabledAgain);

  // Step 5: Probe - whitespace only
  await page.fill('input[type="text"]', '   ');
  const buttonDisabledWhitespace = await button.evaluate(b => b.disabled);
  console.log('button disabled on whitespace:', buttonDisabledWhitespace);

  await browser.close();
})();
