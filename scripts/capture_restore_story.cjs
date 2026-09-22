/* Actual UI captures from one isolated restore run. No DOM content replacement. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function requireCondition(value, message) {
  if (!value) throw new Error(message);
}

async function main() {
  requireCondition(process.argv[2] === '--config' && process.argv.length === 4, 'Expected private --config');
  const config = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const origin = new URL(config.origin);
  requireCondition(origin.protocol === 'http:' && origin.hostname === '127.0.0.1' && origin.port,
    'Capture origin must be an explicit loopback port');
  requireCondition(/^[a-f0-9]{32}$/.test(config.run_id), 'Invalid run ID');
  requireCondition(['imported', 'conflict', 'recovered'].includes(config.phase), 'Invalid capture phase');
  const {chromium, expect} = require(config.playwright_module);
  const edge = process.env.PROGRAMFILES ? path.join(process.env['PROGRAMFILES(X86)'] || process.env.PROGRAMFILES,
    'Microsoft', 'Edge', 'Application', 'msedge.exe') : null;
  const browser = await chromium.launch({headless: true, ...(edge && fs.existsSync(edge) ? {executablePath: edge} : {})});
  const context = await browser.newContext({viewport: {width: 1440, height: 1080}, locale: 'pt-BR', timezoneId: 'America/Sao_Paulo'});
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  const record = {run_id: config.run_id, phase: config.phase, started_at: new Date().toISOString(),
    browser: browser.version(), viewport: {width: 1440, height: 1080}, screenshots: [], observations: {}};
  const get = async route => {
    const response = await context.request.get(config.origin + '/api/v1' + route);
    requireCondition(response.ok(), 'Read-only capture API check failed: ' + route + ' ' + response.status());
    return response.json();
  };
  const shot = async filename => {
    fs.mkdirSync(config.output, {recursive: true});
    const output = path.join(config.output, filename);
    requireCondition(!fs.existsSync(output), 'Capture would overwrite prior evidence');
    await page.screenshot({path: output, fullPage: true, animations: 'disabled'});
    record.screenshots.push({file: filename, sha256: crypto.createHash('sha256').update(fs.readFileSync(output)).digest('hex'),
      captured_at: new Date().toISOString(), full_page: true});
  };
  try {
    await page.goto(config.origin, {waitUntil: 'networkidle'});
    await page.getByLabel('E-mail', {exact: true}).fill(config.email);
    await page.getByLabel('Senha', {exact: true}).fill(config.password);
    await page.getByRole('button', {name: 'Entrar', exact: true}).click();
    await expect(page.getByRole('heading', {name: 'Resumo', exact: true})).toBeVisible();
    const overview = await get('/overview');
    const nav = page.getByRole('navigation', {name: 'Navegação principal'});
    if (config.phase === 'imported' || config.phase === 'conflict') {
      requireCondition(overview.open_cents === '12500' && overview.open_count === 2 && overview.received_cents === '0',
        'Source financial oracle differs');
      const id = config.phase === 'imported' ? config.fixture.batch_id : config.fixture.conflict_batch_id;
      const batch = await get('/imports/' + id);
      const expected = config.phase === 'imported' ? 'confirmed' : 'rejected';
      requireCondition(batch.status === expected && batch.report.row_count === 2, 'Unexpected batch status or row count');
      requireCondition(batch.report.total_cents === (expected === 'confirmed' ? '12500' : '15000'), 'Unexpected batch candidate total');
      if (expected === 'rejected') requireCondition(batch.report.new_count === 0 &&
        batch.report.errors.some(e => e.code === 'existing_conflict'), 'Missing real conflict');
      record.observations = {batch_id: id, status: batch.status, report: batch.report,
        wallet: {open_cents: overview.open_cents, open_count: overview.open_count, received_cents: overview.received_cents}};
      await nav.getByRole('button', {name: 'Importações', exact: true}).click();
      const row = page.getByRole('row').filter({hasText: batch.filename});
      await row.getByRole('button', {name: 'Ver resultado', exact: true}).click();
      const panel = page.getByRole('region', {name: 'Prévia do lote', exact: true});
      await expect(panel.getByRole('heading', {name: batch.filename, exact: true})).toBeVisible();
      await expect(panel.getByText('RESTORE-PAID', {exact: true})).toBeVisible();
      if (expected === 'rejected') await expect(panel.getByText('existing_conflict', {exact: true})).toBeVisible();
      await panel.scrollIntoViewIfNeeded();
      await shot(expected === 'confirmed' ? '01-lote-confirmado.png' : '02-conflito-sem-alteracao-financeira.png');
    } else {
      requireCondition(overview.open_cents === '7500' && overview.received_cents === '5000' && overview.open_count === 1,
        'Recovered financial oracle differs');
      const job = await get('/reminders/' + config.cut.reminder_id);
      const title = await get('/receivables/' + config.fixture.title_ids['RESTORE-PAID']);
      requireCondition(job.status === 'sent' && job.attempts.length === 1 && job.attempts[0].id === config.cut.attempt_id &&
        job.attempts[0].outcome === 'success' && job.delivery && job.delivery.id === config.cut.delivery_id,
        'Recovered reminder/attempt/delivery identity differs');
      requireCondition(title.status === 'paid' && title.payment.id === config.cut.payment_id && title.payment.amount_cents === '5000',
        'Recovered payment identity differs');
      record.observations = {reminder_id: job.id, attempt_id: job.attempts[0].id, attempt_number: job.attempts[0].number,
        attempt_outcome: job.attempts[0].outcome, delivery_id: job.delivery.id, payment_id: title.payment.id,
        title_id: title.id, payment_cents: title.payment.amount_cents,
        wallet: {open_cents: overview.open_cents, open_count: overview.open_count, received_cents: overview.received_cents}};
      await nav.getByRole('button', {name: 'Lembretes', exact: true}).click();
      await page.getByRole('button', {name: 'Ver tentativas', exact: true}).click();
      await expect(page.getByRole('heading', {name: 'Lembrete #' + job.id, exact: true})).toBeVisible();
      await expect(page.getByText('Entrega simulada #' + job.delivery.id, {exact: true})).toBeVisible();
      await shot('03-mesma-tentativa-reconciliada.png');
      await nav.getByRole('button', {name: 'Títulos', exact: true}).click();
      await page.getByRole('button', {name: 'RESTORE-PAID', exact: true}).click();
      await expect(page.getByRole('heading', {name: 'RESTORE-PAID', exact: true})).toBeVisible();
      await expect(page.getByRole('region', {name: 'Dados do título'}).getByText('Pagamento integral', {exact: true})).toBeVisible();
      await shot('04-mesma-baixa-preservada.png');
    }
    record.finished_at = new Date().toISOString();
    record.scope = 'Actual rendered pages; post-login read-only HTTP checks; no DOM replacements, seeding or financial UI writes.';
    process.stdout.write(JSON.stringify(record) + '\n');
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
