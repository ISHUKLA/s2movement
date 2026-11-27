import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.dirname(fileURLToPath(import.meta.url));
const file = await FileBlob.load(path.join(root, "coordinator", "timing-and-scoring.xlsx"));
const book = await SpreadsheetFile.importXlsx(file);
const times = book.worksheets.getItem("Times");
const blind = book.worksheets.getItem("Blind adjudication");
const rates = book.worksheets.getItem("Detection rates");
const methods = ["Tool", "Excel", "Tool", "Excel", "Excel", "Tool", "Excel", "Tool", "Tool", "Excel", "Tool", "Excel", "Excel", "Tool", "Excel", "Tool"];
for (let i = 0; i < 8; i++) {
  const row = i + 5;
  const first = methods[2 * i], second = methods[2 * i + 1];
  times.getRange(`D${row}`).values = [[first]];
  times.getRange(`I${row}`).values = [[second]];
  const day = 46000 + i;
  times.getRange(`E${row}:F${row}`).values = [[day, day + (first === "Excel" ? 60 : 30) / 1440]];
  times.getRange(`J${row}:K${row}`).values = [[day + 0.2, day + 0.2 + (second === "Excel" ? 60 : 30) / 1440]];
}
blind.getRange("D5:D36").values = [[1]];
for (let i = 0; i < 16; i++) rates.getRange(`H${i + 4}`).values = [[methods[i]]];
book.recalculate();
const reduction = times.getRange("B14").values[0][0];
const gate = times.getRange("D14").values[0][0];
assert.ok(typeof reduction === "number" && Math.abs(reduction - 0.5) < 1e-8, `median ${reduction}`);
assert.equal(gate, "PASS");
for (let row = 4; row <= 7; row++) {
  assert.equal(rates.getRange(`C${row}`).values[0][0], 8);
  assert.equal(rates.getRange(`D${row}`).values[0][0], 8);
  assert.equal(rates.getRange(`E${row}`).values[0][0], 1);
}
console.log("Trial formula check: median 50%, gate PASS, all four detection rates 8/8 = 100%.");
