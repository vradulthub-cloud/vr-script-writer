/**
 * VR Script Writer — Google Apps Script
 * =======================================
 * Adds a "Script Writer" custom menu to the 2026 Scripts sheet.
 *
 * HOW TO INSTALL:
 *   1. Open the 2026 Scripts Google Sheet
 *   2. Click Extensions → Apps Script
 *   3. Delete any existing code and paste this entire file
 *   4. Click Save (Ctrl+S), then click Run → onOpen to authorize
 *   5. Refresh the sheet — you'll see a "Script Writer" menu
 *
 * The menu marks rows with a STATUS flag in column K.
 * The daily Python runner reads those flags and generates scripts automatically.
 *
 * For instant regeneration (without waiting for the daily run):
 *   Run the Python script manually:
 *   python3 /Users/andrewninn/Scripts/daily_script_runner.py
 */

const STATUS_COL   = 13;  // Column M (1-indexed) — A=1 … K=11 Title, L=12 Props, M=13 Status
const STATUS_REGEN = "REGEN";
const STATUS_DONE  = "DONE";

const SKIP_TABS = ["Cancellations", "Script Locker", "Template"];
const STUDIO_COL = 2;   // B
const FEMALE_COL = 5;   // E
const PLOT_COL   = 10;  // J

// ── Menu setup ───────────────────────────────────────────────────────────────

const SCRIPT_WRITER_URL = "https://vr-scrip-b6nydgpavverp7zhcrqlx3.streamlit.app";

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("✍️ Script Writer")
    .addItem("🚀 Open Script Writer App", "openScriptWriterApp")
    .addSeparator()
    .addItem("Generate Missing Scripts (this tab)", "generateMissingThisTab")
    .addItem("Generate Missing Scripts (all months)", "generateMissingAll")
    .addSeparator()
    .addItem("Regenerate This Row", "regenThisRow")
    .addItem("Regenerate by Talent Name...", "regenByTalent")
    .addSeparator()
    .addItem("Clear All REGEN Flags (this tab)", "clearRegenThisTab")
    .addToUi();
}

function openScriptWriterApp() {
  var html = HtmlService.createHtmlOutput(
    '<script>window.open("' + SCRIPT_WRITER_URL + '", "_blank"); google.script.host.close();</script>'
  ).setWidth(10).setHeight(10);
  SpreadsheetApp.getUi().showModalDialog(html, "Opening Script Writer...");
}

// ── Helper: mark a row ───────────────────────────────────────────────────────

function markRow(sheet, rowIndex, status) {
  sheet.getRange(rowIndex, STATUS_COL).setValue(status);
}

function rowHasData(row) {
  const studio = row[STUDIO_COL - 1] ? row[STUDIO_COL - 1].toString().trim() : "";
  const female = row[FEMALE_COL - 1] ? row[FEMALE_COL - 1].toString().trim() : "";
  return studio.length > 0 && female.length > 0;
}

function isMonthTab(sheet) {
  return !SKIP_TABS.includes(sheet.getName());
}

// ── Mark missing (no plot) ───────────────────────────────────────────────────

function markMissingInSheet(sheet) {
  const data = sheet.getDataRange().getValues();
  let count = 0;
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const plot   = row[PLOT_COL - 1] ? row[PLOT_COL - 1].toString().trim() : "";
    const status = row[STATUS_COL - 1] ? row[STATUS_COL - 1].toString().trim().toUpperCase() : "";
    if (rowHasData(row) && !plot && status !== STATUS_DONE) {
      markRow(sheet, i + 1, STATUS_REGEN);
      count++;
    }
  }
  return count;
}

function generateMissingThisTab() {
  const sheet = SpreadsheetApp.getActiveSheet();
  if (!isMonthTab(sheet)) {
    SpreadsheetApp.getUi().alert("This tab is not a shoot month tab.");
    return;
  }
  const count = markMissingInSheet(sheet);
  SpreadsheetApp.getUi().alert(
    count > 0
      ? `✅ Marked ${count} row(s) for generation.\n\nRun the daily Python script to generate them now, or wait for the automatic daily run.`
      : "Nothing to generate — all rows already have scripts."
  );
}

function generateMissingAll() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let total = 0;
  ss.getSheets().filter(isMonthTab).forEach(sheet => {
    total += markMissingInSheet(sheet);
  });
  SpreadsheetApp.getUi().alert(
    total > 0
      ? `✅ Marked ${total} row(s) across all months for generation.\n\nRun the daily Python script to generate them now, or wait for the automatic daily run.`
      : "Nothing to generate — all rows already have scripts."
  );
}

// ── Regenerate controls ──────────────────────────────────────────────────────

function regenThisRow() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const row   = SpreadsheetApp.getActiveRange().getRow();
  if (row < 2) {
    SpreadsheetApp.getUi().alert("Select a data row (not the header).");
    return;
  }
  markRow(sheet, row, STATUS_REGEN);
  const female = sheet.getRange(row, FEMALE_COL).getValue();
  SpreadsheetApp.getUi().alert(`✅ Marked row ${row} (${female}) for regeneration.`);
}

function regenByTalent() {
  const ui = SpreadsheetApp.getUi();
  const response = ui.prompt(
    "Regenerate by Talent",
    "Enter the female model's name:",
    ui.ButtonSet.OK_CANCEL
  );
  if (response.getSelectedButton() !== ui.Button.OK) return;

  const name = response.getResponseText().trim().toLowerCase();
  if (!name) return;

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let count = 0;

  ss.getSheets().filter(isMonthTab).forEach(sheet => {
    const data = sheet.getDataRange().getValues();
    for (let i = 1; i < data.length; i++) {
      const female = data[i][FEMALE_COL - 1] ? data[i][FEMALE_COL - 1].toString().trim().toLowerCase() : "";
      if (female === name) {
        markRow(sheet, i + 1, STATUS_REGEN);
        count++;
      }
    }
  });

  ui.alert(
    count > 0
      ? `✅ Marked ${count} row(s) for "${response.getResponseText().trim()}".\n\nRun the Python script or wait for the daily run.`
      : `No rows found for "${response.getResponseText().trim()}".`
  );
}

function regenAllInSheet(sheet) {
  const data = sheet.getDataRange().getValues();
  let count = 0;
  for (let i = 1; i < data.length; i++) {
    if (rowHasData(data[i])) {
      markRow(sheet, i + 1, STATUS_REGEN);
      count++;
    }
  }
  return count;
}

function regenAllThisTab() {
  const sheet = SpreadsheetApp.getActiveSheet();
  if (!isMonthTab(sheet)) {
    SpreadsheetApp.getUi().alert("This tab is not a shoot month tab.");
    return;
  }
  const count = regenAllInSheet(sheet);
  SpreadsheetApp.getUi().alert(`✅ Marked all ${count} row(s) in "${sheet.getName()}" for regeneration.`);
}

function regenAllMonths() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let total = 0;
  ss.getSheets().filter(isMonthTab).forEach(sheet => {
    total += regenAllInSheet(sheet);
  });
  SpreadsheetApp.getUi().alert(`✅ Marked ${total} row(s) across all months for regeneration.`);
}

// ── Cleanup ──────────────────────────────────────────────────────────────────

function clearRegenThisTab() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const data  = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    const status = data[i][STATUS_COL - 1] ? data[i][STATUS_COL - 1].toString().trim().toUpperCase() : "";
    if (status === STATUS_REGEN) {
      markRow(sheet, i + 1, "");
    }
  }
  SpreadsheetApp.getUi().alert("Cleared all REGEN flags on this tab.");
}
