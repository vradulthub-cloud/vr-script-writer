// ============================================================
// Model Search — Apps Script for Model Booking List
// Paste ALL of this into Extensions → Apps Script, then Save.
// Run setupTrigger() once to activate the onEdit listener.
// ============================================================

var SKIP_TABS  = ['📋 Legend', '🔍 Search', 'Export', '📊 Dashboard'];
var HEADER_ROW = 2;   // 0-indexed (row 3 in sheet)
var DATA_START = 3;   // 0-indexed (row 4 in sheet)

// Row numbers (1-indexed, as used by getRange/setValues)
var STATUS_ROW  = 5;   // Green status row — "Type a name..." or "X results found"
var COL_HDR_ROW = 9;   // Permanent column header row (always visible)
var DATA_ROW    = 10;  // First results data row

// Adds "🔍 Search Tools" to the menu bar when the sheet opens
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🔍 Search Tools')
    .addItem('Export Results to CSV (Google Drive)', 'exportToCSV')
    .addItem('Clear Search',                         'clearSearch')
    .addSeparator()
    .addItem('Set up auto-search trigger',           'setupTrigger')
    .addToUi();
}

// Format a value — converts Date objects to "Mon YYYY" strings
function formatVal(val) {
  if (val instanceof Date && !isNaN(val.getTime())) {
    var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return months[val.getMonth()] + ' ' + val.getFullYear();
  }
  return val;
}

// Write the status message to A5 (the green status row)
function setStatus(searchSheet, msg, bgColor, fgColor) {
  var cell = searchSheet.getRange('A' + STATUS_ROW);
  cell.setValue(msg);
  cell.setBackground(bgColor  || '#e8f5e9');
  cell.setFontColor(fgColor   || '#1b5e20');
  cell.setFontWeight('normal');
  cell.setFontSize(10);
}

// Called by the onEdit trigger whenever the user types in B3
function runSearch() {
  var ss          = SpreadsheetApp.getActiveSpreadsheet();
  var searchSheet = ss.getSheetByName('🔍 Search');
  if (!searchSheet) return;

  var query = searchSheet.getRange('B3').getValue().toString().trim().toLowerCase();

  // Clear previous results (row DATA_ROW onward); leave row COL_HDR_ROW intact
  searchSheet.getRange(DATA_ROW, 1, Math.max(searchSheet.getLastRow() - DATA_ROW + 1, 1), 30).clearContent();
  searchSheet.getRange(DATA_ROW, 1, Math.max(searchSheet.getLastRow() - DATA_ROW + 1, 1), 30).clearFormat();

  if (!query) {
    setStatus(searchSheet, 'Type a name in the search box to find a model across all agency tabs.');
    return;
  }

  var results    = [];
  var allHeaders = [];
  var sheets     = ss.getSheets();

  for (var i = 0; i < sheets.length; i++) {
    var ws = sheets[i];
    if (SKIP_TABS.indexOf(ws.getName()) !== -1) continue;

    var data = ws.getDataRange().getValues();
    if (data.length <= DATA_START) continue;

    var headers = data[HEADER_ROW];
    if (allHeaders.length === 0) allHeaders = headers;

    var nameIdx = -1;
    for (var h = 0; h < headers.length; h++) {
      if (headers[h].toString().trim() === 'Name') { nameIdx = h; break; }
    }
    if (nameIdx < 0) continue;

    for (var r = DATA_START; r < data.length; r++) {
      var row     = data[r];
      var rawName = row[nameIdx].toString();
      // Strip =HYPERLINK("url","name") formula if present
      var name    = rawName.replace(/=HYPERLINK\("[^"]*",\s*"([^"]*)"\)/i, '$1').trim();
      if (!name) continue;
      if (name.toLowerCase().indexOf(query) !== -1) {
        // Format each value — converts Date objects to "Mon YYYY"
        var formattedRow = row.map(formatVal);
        results.push([ws.getName()].concat(formattedRow));
      }
    }
  }

  if (results.length === 0) {
    setStatus(searchSheet,
      'No models found matching "' + query + '"',
      '#fce8e6', '#c62828');
    return;
  }

  // Status in the green row (A5)
  setStatus(searchSheet,
    results.length + ' result(s) found for "' + query + '"',
    '#e8f5e9', '#1b5e20');
  searchSheet.getRange('A' + STATUS_ROW).setFontWeight('bold');

  // Update column header row (row 9) with actual headers from the first tab
  var headerRow = ['Agency'].concat(allHeaders);
  var hdrRange  = searchSheet.getRange(COL_HDR_ROW, 1, 1, headerRow.length);
  hdrRange.setValues([headerRow]);
  hdrRange.setBackground('#1a237e');
  hdrRange.setFontColor('#ffffff');
  hdrRange.setFontWeight('bold');
  hdrRange.setFontSize(9);
  hdrRange.setVerticalAlignment('middle');
  hdrRange.setWrap(false);

  // Results rows starting at row DATA_ROW (row 10)
  var dataRange = searchSheet.getRange(DATA_ROW, 1, results.length, results[0].length);
  dataRange.setValues(results);
  dataRange.setFontSize(9);
  dataRange.setVerticalAlignment('middle');

  // Alternate row shading
  for (var row = 0; row < results.length; row++) {
    var bg = (row % 2 === 0) ? '#ffffff' : '#f3f4f6';
    searchSheet.getRange(DATA_ROW + row, 1, 1, results[row].length).setBackground(bg);
  }

  // Bold the Agency column
  searchSheet.getRange(DATA_ROW, 1, results.length, 1).setFontWeight('bold');

  // Set row heights
  searchSheet.setRowHeightsForced(DATA_ROW, results.length, 20);

  // Auto-resize result columns then cap the wide ones
  var numCols = results[0].length;
  for (var c = 1; c <= numCols; c++) {
    searchSheet.autoResizeColumn(c);
  }
  // Col index (1-based): 1=Agency, 2=Name, 6=Location, 7=Available For, 16=Notes
  // (17-19=SLR stats, 20-22=VRP/POVR, 23=OnlyFans, 24=Twitter, 25=Instagram, 26=Bookings, 27=Last Booked)
  var caps = {1: 150, 2: 195, 6: 100, 7: 260, 16: 240};
  for (var cap in caps) {
    var ci = parseInt(cap);
    if (ci <= numCols && searchSheet.getColumnWidth(ci) > caps[cap]) {
      searchSheet.setColumnWidth(ci, caps[cap]);
    }
  }
}

// Clears the search box and results; leaves column header row (row 9) intact
function clearSearch() {
  var ss          = SpreadsheetApp.getActiveSpreadsheet();
  var searchSheet = ss.getSheetByName('🔍 Search');
  if (!searchSheet) return;
  searchSheet.getRange('B3').clearContent();
  // Clear results area only (rows DATA_ROW+), leave row 9 headers
  var lastRow = Math.max(searchSheet.getLastRow(), DATA_ROW);
  searchSheet.getRange(DATA_ROW, 1, lastRow - DATA_ROW + 1, 30).clearContent();
  searchSheet.getRange(DATA_ROW, 1, lastRow - DATA_ROW + 1, 30).clearFormat();
  setStatus(searchSheet, 'Type a name in the search box to find a model across all agency tabs.');
}

// Exports current search results to a CSV file in Google Drive
function exportToCSV() {
  var ss          = SpreadsheetApp.getActiveSpreadsheet();
  var searchSheet = ss.getSheetByName('🔍 Search');
  if (!searchSheet) return;

  var query   = searchSheet.getRange('B3').getValue().toString().trim();
  var lastRow = searchSheet.getLastRow();
  if (lastRow < DATA_ROW) {
    SpreadsheetApp.getUi().alert('No search results to export. Run a search first.');
    return;
  }

  var lastCol = searchSheet.getLastColumn();
  // Export from header row (COL_HDR_ROW) through last data row
  var data = searchSheet.getRange(COL_HDR_ROW, 1, lastRow - COL_HDR_ROW + 1, lastCol).getValues();

  // Build CSV string
  var csv = data.map(function(row) {
    return row.map(function(cell) {
      var val = formatVal(cell).toString().replace(/"/g, '""');
      return '"' + val + '"';
    }).join(',');
  }).join('\n');

  var today    = new Date().toISOString().slice(0, 10);
  var safeName = query.replace(/[^a-zA-Z0-9_\- ]/g, '').replace(/\s+/g, '_') || 'search';
  var fileName = 'model_search_' + safeName + '_' + today + '.csv';

  var file = DriveApp.createFile(fileName, csv, MimeType.CSV);

  SpreadsheetApp.getUi().alert(
    '✅ CSV exported to Google Drive!\n\n' +
    'File: ' + fileName + '\n\n' +
    'Find it at drive.google.com → My Drive\n' +
    '(or search for "' + fileName + '")'
  );
}

// Installs the onEdit trigger — run this once manually
function setupTrigger() {
  var ss      = SpreadsheetApp.getActiveSpreadsheet();
  var triggers = ScriptApp.getProjectTriggers();

  // Remove existing onEdit triggers to avoid duplicates
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'onEditTrigger') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }

  ScriptApp.newTrigger('onEditTrigger')
    .forSpreadsheet(ss)
    .onEdit()
    .create();

  SpreadsheetApp.getUi().alert('✅ Auto-search trigger installed!\n\nNow when you type in the Search tab, results will appear automatically.');
}

// Installable onEdit trigger handler (has elevated permissions vs simple onEdit)
function onEditTrigger(e) {
  try {
    if (!e || !e.source) return;
    var sheet = e.range.getSheet();
    if (sheet.getName() !== '🔍 Search') return;
    if (e.range.getRow() !== 3 || e.range.getColumn() !== 2) return;
    runSearch();
  } catch (err) {
    // Silently fail — don't interrupt the user
  }
}
