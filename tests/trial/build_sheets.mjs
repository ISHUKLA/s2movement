import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.dirname(fileURLToPath(import.meta.url));
const navy = "#17324F";
const pale = "#EAF1F7";

async function save(workbook, target, previewRange, previewSheet) {
  workbook.recalculate();
  const image = await workbook.render({sheetName: previewSheet, range: previewRange, scale: 1.5, format: "png"});
  await fs.writeFile(target.replace(/\.xlsx$/, ".png"), new Uint8Array(await image.arrayBuffer()));
  const blob = await SpreadsheetFile.exportXlsx(workbook);
  await blob.save(target);
}

function title(sheet, text, right = "F") {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${right}1`).merge();
  sheet.getRange("A1").values = [[text]];
  sheet.getRange(`A1:${right}1`).format = {fill: navy, font: {name: "Arial", size: 16, bold: true, color: "#FFFFFF"}};
  sheet.getRange("A1:F1").format.rowHeight = 30;
}

function header(sheet, range) {
  sheet.getRange(range).format = {fill: pale, font: {name: "Arial", bold: true, color: navy}};
}

for (const caseId of ["A", "B"]) {
  const folder = path.join(root, "materials", caseId);
  const data = JSON.parse(await fs.readFile(path.join(root, "build-data", `${caseId}.json`), "utf8"));
  const book = Workbook.create();
  const sheet = book.worksheets.add("Plain cell diff");
  const meta = book.worksheets.add("Metadata diff");
  title(sheet, `Case ${caseId} · plain Excel cell diff`);
  sheet.getRange("A2:F2").merge();
  sheet.getRange("A2").values = [["Opening and closing values shown as reported; movement is closing minus opening."]];
  sheet.getRange("A4:F4").values = [["Template", "Row", "Column", "Opening", "Closing", "Movement"]];
  header(sheet, "A4:F4");
  const rows = data.cells.map(record => [record.template, record.row, record.column, record.opening ?? "", record.closing ?? "", null]);
  sheet.getRange(`A5:F${rows.length + 4}`).values = rows;
  for (let i = 0; i < rows.length; i++) {
    const at = i + 5;
    if (typeof rows[i][3] === "number" && typeof rows[i][4] === "number")
      sheet.getRange(`F${at}`).formulas = [[`=E${at}-D${at}`]];
    else sheet.getRange(`F${at}`).values = [["n/a"]];
  }
  sheet.getRange(`D5:F${rows.length + 4}`).setNumberFormat("#,##0.####");
  sheet.getRange("A:A").format.columnWidth = 24;
  sheet.getRange("B:C").format.columnWidth = 13;
  sheet.getRange("D:F").format.columnWidth = 21;
  sheet.freezePanes.freezeRows(4);

  title(meta, `Case ${caseId} · metadata diff`, "D");
  meta.getRange("A3:D3").values = [["Field", "Opening", "Closing", "Same?"]];
  header(meta, "A3:D3");
  const fields = Object.keys(data.metadata.opening);
  meta.getRange(`A4:C${fields.length + 3}`).values = fields.map(k => [k, data.metadata.opening[k], data.metadata.closing[k]]);
  for (let i = 0; i < fields.length; i++) {
    const at = i + 4;
    meta.getRange(`D${at}`).formulas = [[`=IF(B${at}=C${at},"yes","no")`]];
  }
  meta.getRange("A:A").format.columnWidth = 27;
  meta.getRange("B:C").format.columnWidth = 27;
  meta.getRange("D:D").format.columnWidth = 12;
  await save(book, path.join(folder, "plain-excel-diff.xlsx"), "A1:F12", "Plain cell diff");
}

const assignmentRows = [
  ["R01", "A/tool → B/Excel", "T01", "A", "Tool", "T02", "B", "Excel"],
  ["R02", "A/tool → B/Excel", "T03", "A", "Tool", "T04", "B", "Excel"],
  ["R03", "A/Excel → B/tool", "T05", "A", "Excel", "T06", "B", "Tool"],
  ["R04", "A/Excel → B/tool", "T07", "A", "Excel", "T08", "B", "Tool"],
  ["R05", "B/tool → A/Excel", "T09", "B", "Tool", "T10", "A", "Excel"],
  ["R06", "B/tool → A/Excel", "T11", "B", "Tool", "T12", "A", "Excel"],
  ["R07", "B/Excel → A/tool", "T13", "B", "Excel", "T14", "A", "Tool"],
  ["R08", "B/Excel → A/tool", "T15", "B", "Excel", "T16", "A", "Tool"],
];
const assignment = Workbook.create();
const assign = assignment.worksheets.add("Coordinator only");
title(assign, "Blinded reviewer assignment", "H");
assign.getRange("A3:H3").values = [["Reviewer", "Sequence", "Run 1 blind ID", "Case", "Method", "Run 2 blind ID", "Case", "Method"]];
header(assign, "A3:H3");
assign.getRange("A4:H11").values = assignmentRows;
assign.getRange("A:H").format.columnWidth = 20;
assign.getRange("B:B").format.columnWidth = 27;
await save(assignment, path.join(root, "coordinator", "assignment.xlsx"), "A1:H11", "Coordinator only");

const scoring = Workbook.create();
const times = scoring.worksheets.add("Times");
const adjudication = scoring.worksheets.add("Blind adjudication");
const rates = scoring.worksheets.add("Detection rates");
title(times, "Reviewer trial · times and utility gate", "O");
times.getRange("A2:O2").merge();
times.getRange("A2").values = [["Enter timestamps when materials open and first written issue list is submitted. Enter or paste method labels only after blind adjudication."]];
times.getRange("A4:O4").values = [["Reviewer", "Sequence", "Run 1 ID", "Method", "Opened", "Submitted", "Minutes", "Run 2 ID", "Method", "Opened", "Submitted", "Minutes", "Excel min", "Tool min", "Reduction"]];
header(times, "A4:O4");
for (let i = 0; i < 8; i++) {
  const row = i + 5;
  const a = assignmentRows[i];
  times.getRange(`A${row}:C${row}`).values = [[a[0], a[1], a[2]]];
  times.getRange(`H${row}`).values = [[a[5]]];
  times.getRange(`G${row}`).formulas = [[`=IF(OR(E${row}="",F${row}=""),"",(F${row}-E${row})*1440)`]];
  times.getRange(`L${row}`).formulas = [[`=IF(OR(J${row}="",K${row}=""),"",(K${row}-J${row})*1440)`]];
  times.getRange(`M${row}`).formulas = [[`=IF(OR(D${row}="",I${row}="",G${row}="",L${row}=""),"",IF(D${row}="Excel",G${row},L${row}))`]];
  times.getRange(`N${row}`).formulas = [[`=IF(M${row}="","",IF(D${row}="Tool",G${row},L${row}))`]];
  times.getRange(`O${row}`).formulas = [[`=IF(OR(M${row}="",N${row}="",M${row}=0),"",(M${row}-N${row})/M${row})`]];
}
times.getRange("A14").values = [["Median reduction"]];
times.getRange("B14").formulas = [["=IF(COUNT(O5:O12)=8,MEDIAN(O5:O12),\"\")"]];
times.getRange("C14").values = [[0.35]];
times.getRange("D14").formulas = [["=IF(B14=\"\",\"OPEN\",IF(B14>=C14,\"PASS\",\"FAIL\"))"]];
times.getRange("B14:C14").setNumberFormat("0.0%");
times.getRange("O5:O12").setNumberFormat("0.0%");
times.getRange("E5:F12").setNumberFormat("yyyy-mm-dd hh:mm");
times.getRange("J5:K12").setNumberFormat("yyyy-mm-dd hh:mm");
times.getRange("G5:G12").setNumberFormat("0.0");
times.getRange("L5:N12").setNumberFormat("0.0");
times.getRange("A:O").format.columnWidth = 15;
times.getRange("B:B").format.columnWidth = 25;

title(adjudication, "Blind defect adjudication", "D");
adjudication.getRange("A2:D2").merge();
adjudication.getRange("A2").values = [["Score anonymized first written findings against the separate answer key; keep method labels hidden until all counts are fixed."]];
adjudication.getRange("A4:D4").values = [["Blind run ID", "Defect class", "Opportunities", "Correctly identified"]];
header(adjudication, "A4:D4");
const allIds = assignmentRows.flatMap(r => [r[2], r[5]]).sort();
let rr = 5;
for (const id of allIds) for (const klass of ["Cross-template", "Comparability"]) {
  adjudication.getRange(`A${rr}:C${rr}`).values = [[id, klass, 1]];
  rr++;
}
adjudication.getRange("A:D").format.columnWidth = 24;

title(rates, "Detection by defect class", "E");
rates.getRange("A3:E3").values = [["Class", "Method", "Correct", "Opportunities", "Rate"]];
header(rates, "A3:E3");
rates.getRange("A4:B7").values = [["Cross-template", "Excel"], ["Cross-template", "Tool"], ["Comparability", "Excel"], ["Comparability", "Tool"]];
rates.getRange("G3:H3").values = [["Blind run ID", "Method after reveal"]];
header(rates, "G3:H3");
rates.getRange("G4:G19").values = allIds.map(id => [id]);
for (let row = 4; row <= 7; row++) {
  const cls = `A${row}`, method = `B${row}`;
  rates.getRange(`C${row}`).formulas = [[`=IF(COUNT('Blind adjudication'!$D$5:$D$36)<32,"",SUMIFS('Blind adjudication'!$D$5:$D$36,'Blind adjudication'!$B$5:$B$36,${cls},$H$22:$H$53,${method}))`]];
  // These two formula cells are populated by the coordinator after copying the
  // blind IDs and methods into the reveal columns on this sheet.
  rates.getRange(`D${row}`).formulas = [[`=IF(C${row}="","",COUNTIFS($G$22:$G$53,${cls},$H$22:$H$53,${method}))`]];
  rates.getRange(`E${row}`).formulas = [[`=IF(OR(D${row}="",D${row}=0),"",C${row}/D${row})`]];
}
rates.getRange("G21:H21").values = [["Class after reveal", "Method after reveal"]];
for (let row = 22; row <= 53; row++) {
  const sourceRow = row - 17;
  rates.getRange(`G${row}`).formulas = [[`='Blind adjudication'!B${sourceRow}`]];
  rates.getRange(`H${row}`).formulas = [[`=IFERROR(VLOOKUP('Blind adjudication'!A${sourceRow},$G$4:$H$19,2,FALSE),"")`]];
}
rates.getRange("A:A").format.columnWidth = 24;
rates.getRange("B:H").format.columnWidth = 23;
rates.getRange("E4:E7").setNumberFormat("0.0%");
await save(scoring, path.join(root, "coordinator", "timing-and-scoring.xlsx"), "A1:O15", "Times");

const blind = Workbook.create();
const blindSheet = blind.worksheets.add("Adjudication");
title(blindSheet, "Blind issue scoring", "D");
blindSheet.getRange("A2:D2").merge();
blindSheet.getRange("A2").values = [["Score anonymized first written findings. Method labels are supplied to the coordinator only after this file is complete."]];
blindSheet.getRange("A4:D4").values = [["Blind run ID", "Defect class", "Opportunities", "Correctly identified (0 or 1)"]];
header(blindSheet, "A4:D4");
let blindRow = 5;
for (const id of allIds) for (const klass of ["Cross-template", "Comparability"]) {
  blindSheet.getRange(`A${blindRow}:C${blindRow}`).values = [[id, klass, 1]];
  blindRow++;
}
blindSheet.getRange("A:D").format.columnWidth = 27;
await save(blind, path.join(root, "coordinator", "blind-adjudication.xlsx"), "A1:D13", "Adjudication");
