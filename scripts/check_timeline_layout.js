#!/usr/bin/env node
"use strict";

const fs = require("fs");
const vm = require("vm");

const input = process.argv[2];
if (!input) {
  process.stderr.write("usage: check_timeline_layout.js <rendered-index.html>\n");
  process.exit(2);
}

class ElementStub {
  constructor() {
    this.children = [];
    this.dataset = {};
    this.style = { setProperty() {} };
    this.classList = { toggle() {}, add() {}, remove() {} };
    this.value = "";
    this.innerHTML = "";
    this.textContent = "";
  }
  appendChild(child) {
    this.children.push(child);
    return child;
  }
  setAttribute(name, value) { this[name] = String(value); }
  addEventListener() {}
  querySelectorAll() { return []; }
}

const elements = new Map();
global.document = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, new ElementStub());
    return elements.get(id);
  },
  createElement() { return new ElementStub(); },
};
global.localStorage = { getItem() { return null; }, setItem() {} };

const html = fs.readFileSync(input, "utf8");
const forbiddenMemoryControls = [
  'id="memoryDialog"',
  'id="addMemory"',
  'id="exportButton"',
  'id="importButton"',
  'id="importFile"',
];
const presentMemoryControls = forbiddenMemoryControls.filter(marker => html.includes(marker));
if (presentMemoryControls.length) {
  process.stderr.write(`report must be read-only; interactive memory controls found: ${presentMemoryControls.join(", ")}\n`);
  process.exit(1);
}
const parts = html.split("<script>");
if (parts.length !== 2 || !parts[1].includes("</script>")) {
  process.stderr.write("rendered page must contain exactly one inline script\n");
  process.exit(2);
}
vm.runInThisContext(parts[1].split("</script>")[0], { filename: input });

const number = (value, fallback) => {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};
const timelineChildren = elements.get("timeline").children;
const timelinePrompts = timelineChildren
  .filter(element => String(element.className || "").split(/\s+/).includes("gap"));
if (timelinePrompts.length) {
  process.stderr.write(`timeline prompts must render outside the time axis: ${timelinePrompts.length} found\n`);
  process.exit(1);
}

const boxes = timelineChildren
  .filter(element => String(element.className || "").split(/\s+/).includes("event"))
  .map((element, index) => ({
    index,
    top: number(element.style.top, 0),
    height: number(element.style.height, 0),
    left: number(element.style.left, 0),
    width: number(element.style.width, 100),
    title: String(element.innerHTML).match(/event-title\">([^<]+)/)?.[1] || `event-${index}`,
  }));

const overlaps = [];
for (let leftIndex = 0; leftIndex < boxes.length; leftIndex += 1) {
  for (let rightIndex = leftIndex + 1; rightIndex < boxes.length; rightIndex += 1) {
    const left = boxes[leftIndex];
    const right = boxes[rightIndex];
    const vertical = Math.min(left.top + left.height, right.top + right.height) - Math.max(left.top, right.top);
    const horizontal = Math.min(left.left + left.width, right.left + right.width) - Math.max(left.left, right.left);
    if (vertical > 0.5 && horizontal > 0.1) {
      overlaps.push({ left: left.title, right: right.title, vertical_px: Number(vertical.toFixed(2)) });
    }
  }
}

if (overlaps.length) {
  process.stderr.write(`timeline overlap: ${JSON.stringify(overlaps, null, 2)}\n`);
  process.exit(1);
}
process.stdout.write(`timeline layout ok: ${boxes.length} event blocks, 0 overlaps\n`);
