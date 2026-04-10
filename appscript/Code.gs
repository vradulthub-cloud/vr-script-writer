// ─────────────────────────────────────────────────────────────────────────────
// Model Booking List — Profile Sidebar
// Paste this entire file into: Extensions > Apps Script > Code.gs
// Then create a second file called "Sidebar" (HTML) and paste Sidebar.html
// ─────────────────────────────────────────────────────────────────────────────

const HEADER_ROW = 3;  // Row that contains column names

// ── Menu ──────────────────────────────────────────────────────────────────────

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('📋 Model Profiles')
    .addItem('View Selected Model', 'showProfileSidebar')
    .addSeparator()
    .addItem('Enable Auto-Preview on Row Click', 'createSelectionTrigger')
    .addItem('Disable Auto-Preview', 'deleteSelectionTrigger')
    .addToUi();
}


// ── Sidebar ───────────────────────────────────────────────────────────────────

function showProfileSidebar() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const row   = sheet.getActiveCell().getRow();

  if (row <= HEADER_ROW) {
    SpreadsheetApp.getUi().alert('Please click on a model row first, then use the menu.');
    return;
  }
  _renderSidebar(sheet, row);
}


function _renderSidebar(sheet, row) {
  const lastCol  = sheet.getLastColumn();
  const headers  = sheet.getRange(HEADER_ROW, 1, 1, lastCol).getValues()[0];
  const values   = sheet.getRange(row,        1, 1, lastCol).getValues()[0];

  const model = { __row__: row, __tab__: sheet.getName() };
  headers.forEach((h, i) => {
    const key = String(h).trim();
    if (key) model[key] = String(values[i]).trim();
  });

  // Agency from row 1 col A (may be a merged cell label)
  try { model.__agency__ = String(sheet.getRange(1, 1).getValue()).trim(); } catch(e) {}

  const template  = HtmlService.createTemplateFromFile('Sidebar');
  template.modelJson = JSON.stringify(model);

  const html = template.evaluate()
    .setTitle('Model Profile')
    .setWidth(340);

  SpreadsheetApp.getUi().showSidebar(html);
}


// ── Auto-preview trigger ──────────────────────────────────────────────────────

// This is called by the installable trigger (not the simple onSelectionChange)
function onRowSelect(e) {
  try {
    const row = e.range.getRow();
    if (row > HEADER_ROW && e.range.getNumRows() === 1) {
      _renderSidebar(e.source.getActiveSheet(), row);
    }
  } catch(err) {
    // Silently ignore errors in triggers
  }
}


function createSelectionTrigger() {
  const ss       = SpreadsheetApp.getActive();
  const triggers = ScriptApp.getProjectTriggers();

  for (const t of triggers) {
    if (t.getHandlerFunction() === 'onRowSelect') {
      SpreadsheetApp.getUi().alert('Auto-preview is already enabled.');
      return;
    }
  }

  ScriptApp.newTrigger('onRowSelect')
    .forSpreadsheet(ss)
    .onSelectionChange()
    .create();

  SpreadsheetApp.getUi().alert(
    '✅ Auto-preview enabled!\n\nClick any model row to instantly see their profile in the sidebar.'
  );
}


function deleteSelectionTrigger() {
  const triggers = ScriptApp.getProjectTriggers();
  let found = false;
  for (const t of triggers) {
    if (t.getHandlerFunction() === 'onRowSelect') {
      ScriptApp.deleteTrigger(t);
      found = true;
    }
  }
  SpreadsheetApp.getUi().alert(found
    ? 'Auto-preview disabled.'
    : 'Auto-preview was not enabled.');
}
