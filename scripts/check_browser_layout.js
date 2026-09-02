#!/usr/bin/env node

const path = require("node:path");
const {pathToFileURL} = require("node:url");
const {chromium} = require("playwright");

const input = process.argv[2];
const screenshot = process.argv[3];
if (!input || !screenshot) {
  process.stderr.write("usage: check_browser_layout.js <html-or-url> <screenshot.png>\n");
  process.exit(2);
}

const target = /^https?:\/\//.test(input)
  ? input
  : pathToFileURL(path.resolve(input)).href;

(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}, deviceScaleFactor: 1});
  await page.goto(target, {waitUntil: "load"});
  await page.waitForSelector(".event");

  const result = await page.evaluate(() => {
    const cards = [...document.querySelectorAll(".event, .gap")].map((card, index) => {
      const box = card.getBoundingClientRect();
      const title = card.querySelector(".event-title");
      const summary = card.querySelector(".event-summary");
      const prompt = card.querySelector("strong");
      const children = [...card.children].map(child => child.getBoundingClientRect());
      const paddingBottom = Number.parseFloat(getComputedStyle(card).paddingBottom) || 0;
      const contentBottom = children.length ? Math.max(...children.map(child => child.bottom)) : box.top;
      return {
        index,
        kind: card.classList.contains("gap") ? "gap" : "event",
        label: title?.textContent?.trim() || prompt?.textContent?.trim() || `card-${index}`,
        left: box.left,
        right: box.right,
        top: box.top,
        bottom: box.bottom,
        width: box.width,
        height: box.height,
        contentOverflow: Math.max(0, contentBottom - (box.bottom - paddingBottom)),
        titleHeight: title?.getBoundingClientRect().height || 0,
        titleScrollHeight: title?.scrollHeight || 0,
        cardClipped: contentBottom > box.bottom - paddingBottom + 1,
        titleClipped: Boolean(title && (title.scrollHeight > title.clientHeight + 1 || title.scrollWidth > title.clientWidth + 1)),
        summaryClipped: Boolean(summary && (summary.scrollHeight > summary.clientHeight + 1 || summary.scrollWidth > summary.clientWidth + 1)),
      };
    });

    const overlaps = [];
    for (let left = 0; left < cards.length; left += 1) {
      for (let right = left + 1; right < cards.length; right += 1) {
        const a = cards[left];
        const b = cards[right];
        const overlapX = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const overlapY = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (overlapX > 0.5 && overlapY > 0.5) {
          overlaps.push({a: a.label, b: b.label, overlapX, overlapY});
        }
      }
    }

    const timelineScroll = document.querySelector(".timeline-scroll");
    const memoryControlIds = ["memoryDialog", "addMemory", "exportButton", "importButton", "importFile"];
    const dramaticDurationPattern = /(忙到深夜|一路[^。；，]*深夜|奋战到|熬到(?:深夜|凌晨))/;
    return {
      cards,
      overlaps,
      timeline: document.querySelector(".timeline")?.getBoundingClientRect().toJSON(),
      horizontalOverflow: timelineScroll ? Math.max(0, timelineScroll.scrollWidth - timelineScroll.clientWidth) : 0,
      memoryControls: memoryControlIds.filter(id => document.getElementById(id)),
      interactivePrompts: [...document.querySelectorAll(".gap")].filter(prompt => prompt.matches("button, a, [role='button']") || prompt.tabIndex >= 0).map(prompt => prompt.textContent.trim()),
      dramaticDurationCopy: dramaticDurationPattern.test(document.getElementById("daySummary")?.textContent || "") ? [document.getElementById("daySummary").textContent.trim()] : [],
    };
  });

  const detail = await page.evaluate(() => {
    const first = document.querySelector(".event");
    const title = first?.querySelector(".event-title")?.textContent?.trim() || "";
    first?.click();
    const dialog = document.getElementById("eventDialog");
    return {
      opened: Boolean(dialog?.open),
      titleMatches: document.getElementById("eventDetailTitle")?.textContent?.trim() === title,
      hasSummary: Boolean(document.getElementById("eventDetailCopy")?.textContent?.trim()),
    };
  });
  await page.keyboard.press("Escape");

  await page.screenshot({path: path.resolve(screenshot), fullPage: true});
  await browser.close();

  const failures = {
    cardClipped: result.cards.filter(card => card.cardClipped).map(card => ({label: card.label, width: card.width, height: card.height, contentOverflow: card.contentOverflow, titleHeight: card.titleHeight, titleScrollHeight: card.titleScrollHeight})),
    titleClipped: result.cards.filter(card => card.titleClipped).map(card => card.label),
    summaryClipped: result.cards.filter(card => card.summaryClipped).map(card => card.label),
    overlaps: result.overlaps,
    horizontalOverflow: result.horizontalOverflow > 1 ? [{overflowPx: result.horizontalOverflow}] : [],
    memoryControls: result.memoryControls,
    interactivePrompts: result.interactivePrompts,
    dramaticDurationCopy: result.dramaticDurationCopy,
    detailDialog: detail.opened && detail.titleMatches && detail.hasSummary ? [] : [detail],
  };
  const failed = failures.cardClipped.length || failures.titleClipped.length || failures.overlaps.length || failures.horizontalOverflow.length || failures.memoryControls.length || failures.interactivePrompts.length || failures.dramaticDurationCopy.length || failures.detailDialog.length;
  process.stdout.write(`${JSON.stringify({target, screenshot: path.resolve(screenshot), timeline: result.timeline, failures}, null, 2)}\n`);
  process.exit(failed ? 1 : 0);
})().catch(error => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(2);
});
