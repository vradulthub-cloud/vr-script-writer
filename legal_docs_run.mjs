import { readFileSync } from 'fs';
import { homedir } from 'os';

// ---- CONFIG ----
const SHEET_ID    = '1bM1G49p2KK9WY3WfjzPixrWUw8KBiDGKR-0jKw5QUVc';
const ROOT_FOLDER = '132MZR2EgBeEEJRmF3OJke5WnZozkv2cJ';
const FEMALE_TPL  = '1ey06iXodjkOhK6BK-Q9nsQ2UtiaAo5Oc';
const MALE_TPLS   = {
  'MikeMancini':  '1xlbezjCXjTkxBwyI-QdaS4JGyCeESSc-',
  'JaydenMarcos': '13qNXBqrygLrcnMsKI9sZy_3XOYP0Gjok',
  'DannySteele':  '1PxyfZnZZqeOe4DiqNN7AmeQuNcrfXc2j',
};

// ---- LOAD CREDENTIALS ----
const CREDS_PATH = `${homedir()}/.config/google-legal-docs/credentials.json`;
let creds;
try {
  creds = JSON.parse(readFileSync(CREDS_PATH, 'utf8'));
} catch (e) {
  console.error(JSON.stringify({ error: `Cannot read credentials at ${CREDS_PATH}: ${e.message}` }));
  process.exit(1);
}

async function getAccessToken() {
  const params = new URLSearchParams({
    grant_type:    'refresh_token',
    refresh_token: creds.refresh_token,
    client_id:     creds.client_id,
    client_secret: creds.client_secret,
  });
  const res  = await fetch('https://oauth2.googleapis.com/token', { method: 'POST', body: params });
  const data = await res.json();
  if (!data.access_token) throw new Error('Token refresh failed: ' + JSON.stringify(data));
  return data.access_token;
}

function makeApi(accessToken) {
  return async (url, options = {}) => {
    const res = await fetch(url, {
      ...options,
      headers: {
        Authorization:  `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });
    return res.json();
  };
}

(async () => {
  let accessToken;
  try {
    accessToken = await getAccessToken();
  } catch (e) {
    console.error(JSON.stringify({ error: e.message }));
    process.exit(1);
  }

  const g = makeApi(accessToken);

  // ---- DATE HELPERS ----
  const now       = new Date();
  const mm        = String(now.getMonth() + 1).padStart(2, '0');
  const dd        = String(now.getDate()).padStart(2, '0');
  const yy        = String(now.getFullYear()).slice(-2);
  const dateCode  = mm + dd + yy;
  const monthName = now.toLocaleString('en-US', { month: 'long' });
  const sheetTab  = monthName + ' 20' + yy;
  const dateVariants = [`${parseInt(mm)}/${dd}/${yy}`, `${mm}/${dd}/${yy}`];
  const log = [];

  // 1. Read sheet
  const sheetData = await g(
    `https://sheets.googleapis.com/v4/spreadsheets/${SHEET_ID}/values/${encodeURIComponent(sheetTab)}!A:F`
  );
  if (sheetData.error) {
    console.error(JSON.stringify({ error: sheetData.error, step: 'read sheet' }));
    process.exit(1);
  }

  const rows = sheetData.values || [];
  log.push(`Read ${rows.length} rows from "${sheetTab}"`);

  // 2. Find BG shoots for today (Col A = date, Col E = female, Col F = male)
  const shoots = rows
    .filter(r => dateVariants.includes((r[0] || '').trim()) && (r[4] || '').trim() && (r[5] || '').trim())
    .map(r => ({
      female: r[4].trim().replace(/\s+/g, ''),
      male:   r[5].trim().replace(/\s+/g, ''),
    }));

  if (shoots.length === 0) {
    console.log(JSON.stringify({ status: 'No BG shoots today', date: dateCode, month: monthName, totalRows: rows.length, maleFileIds: [] }));
    process.exit(0);
  }

  // 3. Find or create month folder
  const monthSearch = await g(
    `https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(`'${ROOT_FOLDER}' in parents and name='${monthName}' and mimeType='application/vnd.google-apps.folder' and trashed=false`)}&fields=files(id,name)`
  );
  if (monthSearch.error) {
    console.error(JSON.stringify({ error: monthSearch.error, step: 'find month folder' }));
    process.exit(1);
  }

  let monthFolderId;
  if (monthSearch.files && monthSearch.files.length > 0) {
    monthFolderId = monthSearch.files[0].id;
    log.push(`Month folder exists: ${monthName}`);
  } else {
    const created = await g('https://www.googleapis.com/drive/v3/files', {
      method: 'POST',
      body: JSON.stringify({ name: monthName, mimeType: 'application/vnd.google-apps.folder', parents: [ROOT_FOLDER] }),
    });
    if (created.error) {
      console.error(JSON.stringify({ error: created.error, step: 'create month folder' }));
      process.exit(1);
    }
    monthFolderId = created.id;
    log.push(`Created month folder: ${monthName}`);
  }

  // 4. Process each shoot
  const maleFileIds = []; // collect {id, name} for date-filling step

  for (const { female, male } of shoots) {
    const folderName = `${dateCode}-${female}-${male}`;

    // Skip if folder already exists (idempotent)
    const existing = await g(
      `https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(`'${monthFolderId}' in parents and name='${folderName}' and trashed=false`)}&fields=files(id,name)`
    );
    if (existing.files && existing.files.length > 0) {
      log.push(`SKIP (exists): ${folderName}`);
      // Still collect the male file ID for date-filling
      const filesInFolder = await g(
        `https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(`'${existing.files[0].id}' in parents and trashed=false`)}&fields=files(id,name)`
      );
      const maleFile = (filesInFolder.files || []).find(f => f.name.startsWith(male));
      if (maleFile) maleFileIds.push({ id: maleFile.id, name: maleFile.name });
      continue;
    }

    // Create shoot folder
    const dayFolder = await g('https://www.googleapis.com/drive/v3/files', {
      method: 'POST',
      body: JSON.stringify({ name: folderName, mimeType: 'application/vnd.google-apps.folder', parents: [monthFolderId] }),
    });
    if (dayFolder.error) {
      log.push(`ERROR creating folder ${folderName}: ${JSON.stringify(dayFolder.error)}`);
      continue;
    }
    log.push(`Created folder: ${folderName}`);
    const dayFolderId = dayFolder.id;

    const maleTplId = MALE_TPLS[male];
    const copyJobs = [
      g(`https://www.googleapis.com/drive/v3/files/${FEMALE_TPL}/copy`, {
        method: 'POST',
        body: JSON.stringify({ name: `${female}-${dateCode}.pdf`, parents: [dayFolderId] }),
      }),
    ];
    if (maleTplId) {
      copyJobs.push(
        g(`https://www.googleapis.com/drive/v3/files/${maleTplId}/copy`, {
          method: 'POST',
          body: JSON.stringify({ name: `${male}-${dateCode}.pdf`, parents: [dayFolderId] }),
        })
      );
    } else {
      log.push(`  ⚠️ Unknown male model "${male}" — no template on file. Add their template ID to MALE_TPLS.`);
    }

    const results = await Promise.all(copyJobs);
    results.forEach((r, i) => {
      if (r.error) {
        log.push(`  ERROR copying ${i === 0 ? 'female' : 'male'} PDF: ${JSON.stringify(r.error)}`);
      } else {
        log.push(`  + ${r.name}`);
        if (i === 1) maleFileIds.push({ id: r.id, name: r.name }); // male is index 1
      }
    });
  }

  console.log(JSON.stringify({ date: dateCode, month: monthName, actions: log, maleFileIds }));
})();
