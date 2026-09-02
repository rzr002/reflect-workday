#!/usr/bin/env node

const path = require("node:path");
const {pathToFileURL} = require("node:url");
const {chromium} = require("playwright");

const input = process.argv[2];
const screenshot = process.argv[3];
if (!input || !screenshot) {
  process.stderr.write("usage: check_weekly_layout.js <html-or-url> <screenshot.png>\n");
  process.exit(2);
}

const target = /^https?:\/\//.test(input) ? input : pathToFileURL(path.resolve(input)).href;

(async () => {
  const browser = await chromium.launch({headless: true});
  const results = [];
  for (const viewport of [{name: "desktop", width: 1440, height: 1000}, {name: "mobile", width: 390, height: 844}]) {
    const page = await browser.newPage({viewport});
    await page.goto(target, {waitUntil: "load"});
    await page.waitForSelector(".week-row");
    const result = await page.evaluate(() => {
      const rows = [...document.querySelectorAll(".week-row")];
      const dramatic = /(忙到深夜|一路[^。；，]*深夜|奋战到|熬到(?:深夜|凌晨))/;
      return {
        rowCount: rows.length,
        dates: rows.map(row => row.dataset.weekDay),
        pageOverflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
        tableOverflow: Math.max(0, document.querySelector(".table-wrap").scrollWidth - document.querySelector(".table-wrap").clientWidth),
        clippedCells: [...document.querySelectorAll("td")].filter(cell => cell.scrollWidth > cell.clientWidth + 1).map(cell => cell.textContent.trim()),
        memoryControls: ["memoryDialog", "addMemory", "exportButton", "importButton", "importFile"].filter(id => document.getElementById(id)),
        dramaticCopy: dramatic.test(document.body.textContent),
      };
    });
    results.push({...viewport, ...result});
    if (viewport.name === "desktop") await page.screenshot({path: path.resolve(screenshot), fullPage: true});
    await page.close();
  }
  await browser.close();
  const failures = results.flatMap(result => {
    const current = [];
    if (result.rowCount !== 7) current.push(`${result.name}: expected 7 rows, got ${result.rowCount}`);
    if (new Set(result.dates).size !== 7) current.push(`${result.name}: dates are not unique`);
    if (result.pageOverflow > 1 || result.tableOverflow > 1) current.push(`${result.name}: horizontal overflow`);
    if (result.clippedCells.length) current.push(`${result.name}: clipped cells`);
    if (result.memoryControls.length) current.push(`${result.name}: interactive memory controls`);
    if (result.dramaticCopy) current.push(`${result.name}: dramatic duration copy`);
    return current;
  });
  process.stdout.write(`${JSON.stringify({target, screenshot: path.resolve(screenshot), results, failures}, null, 2)}\n`);
  process.exit(failures.length ? 1 : 0);
})().catch(error => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(2);
});
