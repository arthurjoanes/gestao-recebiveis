/* Real application captures and accessibility checks; only disposable demo stacks. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium, firefox, expect } = require(process.env.PLAYWRIGHT_MODULE);

const origin = process.env.REVIEW_ORIGIN;
const output = process.env.REVIEW_OUTPUT;
// Match import history from earlier capture preparations without adding receipts.
const fixtureImports = Number(process.env.REVIEW_FIXTURE_IMPORTS || '1');
if (!Number.isInteger(fixtureImports) || fixtureImports < 1 || fixtureImports > 10)
  throw new Error('Fixture import count must be an integer between 1 and 10');
if (!origin || !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(origin) || !output)
  throw new Error('Explicit loopback origin and isolated output are required');
if (fs.existsSync(output)) throw new Error('Capture output must be new');
fs.mkdirSync(output, { recursive: true });
const fixture = `source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date\nuiux,UIUX-001,UIUX-CUSTOMER,Cliente ficticio da revisao com nome extenso para conferencia operacional,uiux@example.com,Titulo sintetico para revisar parcela e saldo,1250.09,2026-07-18\nuiux,UIUX-002,UIUX-CUSTOMER,Cliente ficticio da revisao com nome extenso para conferencia operacional,uiux@example.com,Titulo sintetico vencido,480.10,2026-05-18\nuiux,UIUX-003,UIUX-CUSTOMER,Cliente ficticio da revisao com nome extenso para conferencia operacional,uiux@example.com,Titulo sintetico em dia,269.81,2026-08-20\n`;
const record = { schema: 1, run_id: process.env.REVIEW_RUN_ID, phase: process.env.REVIEW_PHASE,
  at: new Date().toISOString(), script_sha256: crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),
  fixture_sha256: crypto.createHash('sha256').update(fixture).digest('hex'), screenshots: [], observations: [], console_errors: [], failed_requests: [], accessibility: [] };

async function navigate(page, name) {
  if (await page.getByRole('button', { name: 'Menu', exact: true }).isVisible())
    await page.getByRole('button', { name: 'Menu', exact: true }).click();
  await page.getByRole('navigation', { name: 'Navegação principal' }).getByRole('button', { name, exact: true }).click();
}
async function login(page, role = 'operador') {
  await page.goto(origin);
  await page.getByLabel('E-mail', { exact: true }).fill(`${role}@example.com`);
  await page.getByLabel('Senha', { exact: true }).fill('Recebiveis!2026');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Resumo', exact: true })).toBeVisible();
  await page.locator('.metric-open strong').waitFor();
}
async function shot(page, name, width) {
  const filename = `${name}-${width}.png`;
  const observation = await page.evaluate(() => ({ width: innerWidth, height: innerHeight,
    document_width: document.documentElement.scrollWidth,
    h1: document.querySelector('h1')?.textContent,
    heading_fonts: [...document.querySelectorAll('h1,h2')].filter(e => e.getClientRects().length).map(e => ({ text: e.textContent, size: getComputedStyle(e).fontSize })),
    small_targets: [...document.querySelectorAll('button,a,input,select,textarea,summary')].filter(e => !e.disabled && e.getClientRects().length).map(e => ({ name: e.getAttribute('aria-label') || e.textContent.trim().slice(0,100), width: e.getBoundingClientRect().width, height: e.getBoundingClientRect().height })).filter(e => e.width < 24 || e.height < 24)
  }));
  if (observation.document_width > width) throw new Error(`Page overflow: ${name} ${width} ${observation.document_width}`);
  const file = path.join(output, filename);
  const fullPage = name !== 'parcela';
  await page.screenshot({ path: file, fullPage, animations: 'disabled' });
  record.screenshots.push({ file: filename, name, full_page: fullPage, viewport: {width,height:900}, sha256: crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex') });
  record.observations.push({ name, ...observation });
  if (process.env.AXE_SOURCE) {
    await page.evaluate(fs.readFileSync(process.env.AXE_SOURCE, 'utf8'));
    const scan = await page.evaluate(async () => {
      const value = await axe.run(document, { runOnly: {type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']} });
      return { violations: value.violations.map(v => ({id:v.id,impact:v.impact,help:v.help,helpUrl:v.helpUrl,nodes:v.nodes.map(n=>({target:n.target,failureSummary:n.failureSummary}))})),
        incomplete: value.incomplete.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,failureSummary:n.failureSummary}))})), passes: value.passes.length };
    });
    record.accessibility.push({ name, width, ...scan });
  }
}
async function main() {
  const edge = process.env.REVIEW_BROWSER_PATH;
  const browser = await chromium.launch({ headless: true, ...(edge ? {executablePath:edge} : {}) });
  record.browser = browser.version();
  const context = await browser.newContext({ viewport: {width:1440,height:900}, locale:'pt-BR',timezoneId:'America/Sao_Paulo' });
  const page = await context.newPage();
  page.on('pageerror', e=>record.console_errors.push(e.message));
  page.on('requestfailed', r=>record.failed_requests.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText}));
  try {
    await login(page);
    const session = await (await page.request.get(origin+'/api/v1/auth/session')).json();
    const headers = { Origin:origin, 'X-CSRF-Token':session.csrf_token };
    for (let preparation = 0; preparation < fixtureImports; preparation++) {
      const preview = await page.request.post(origin+'/api/v1/imports',{headers,multipart:{file:{name:'uiux-fixture.csv',mimeType:'text/csv',buffer:Buffer.from(fixture)}}});
      if (!preview.ok()) throw new Error('Fixture preview rejected');
      const batch = await preview.json();
      if (!(await page.request.post(origin+`/api/v1/imports/${batch.id}/confirm`,{headers})).ok()) throw new Error('Fixture confirmation rejected');
    }
    const titles = await (await page.request.get(origin+'/api/v1/receivables?q=UIUX-')).json();
    const partial = titles.items.find(t=>t.external_receivable_id==='UIUX-001');
    const receipt = await page.request.post(origin+`/api/v1/receivables/${partial.id}/payments`,{headers,data:{idempotency_key:'uiux-review-partial-001',amount_cents:'50010',note:'Recebimento sintetico da revisao'}});
    if (!receipt.ok()) throw new Error('Fixture receipt rejected');
    const refreshed = await (await page.request.get(origin+`/api/v1/receivables/${partial.id}`)).json();
    if (refreshed.remaining_cents!=='74999'||refreshed.paid_cents!=='50010') throw new Error('Fixture financial oracle differs');
    record.fixture = { title_id:partial.id,customer_id:partial.customer_id,original_cents:'125009',paid_cents:'50010',remaining_cents:'74999',business_date:'2026-08-17',worker:'not started for paired visual fixture'};
    const importHistory = await (await page.request.get(origin+'/api/v1/imports')).json();
    record.fixture.import_history_total = importHistory.total;
    record.fixture.setup_imports = fixtureImports;
    const overview = await (await page.request.get(origin+'/api/v1/overview')).json();
    record.fixture.overview = { open_cents:overview.open_cents,received_cents:overview.received_cents,open_count:overview.open_count,paid_count:overview.paid_count };
    // The fixture was prepared through the real API after the first overview load.
    // Reload removes that earlier position before the first paired capture.
    await page.reload();
    await expect(page.getByRole('heading',{name:'Resumo',exact:true})).toBeVisible();
    for (const width of [1440,1024,768,390,320]) {
      await page.setViewportSize({width,height:900});
      await navigate(page,'Resumo');
      await page.locator('.metric-open strong').waitFor();
      const cents = BigInt(overview.open_cents);
      const expectedMoney = `R$ ${(cents/100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g,'.')},${(cents%100n).toString().padStart(2,'0')}`;
      await expect(page.locator('.metric-open strong')).toHaveText(expectedMoney);
      await shot(page,'resumo',width);
      await navigate(page,'Títulos');
      if (!(await page.getByLabel('Cliente ou título',{exact:true}).isVisible())) await page.getByRole('button',{name:'Filtrar carteira',exact:true}).click();
      await page.getByLabel('Cliente ou título',{exact:true}).fill('UIUX-');
      await page.getByRole('button',{name:'Filtrar títulos',exact:true}).click();
      await page.getByRole('button',{name:'UIUX-001',exact:true}).waitFor();
      await shot(page,'carteira',width);
      await page.getByRole('button',{name:'UIUX-001',exact:true}).click();
      await page.getByRole('heading',{name:'Recebimentos (1)',exact:true}).waitFor();
      await shot(page,'titulo',width);
      await page.getByRole('button',{name:'Registrar pagamento',exact:true}).click();
      await page.getByRole('combobox',{name:'Tipo de recebimento',exact:true}).selectOption('partial');
      await page.getByRole('textbox',{name:/Valor recebido \(R\$\)|Valor em reais/}).fill('100,01');
      await shot(page,'parcela',width);
      await page.getByRole('button',{name:'Fechar diálogo',exact:true}).click();
      await page.getByRole('button',{name:'Extrato do cliente',exact:true}).click();
      await page.getByRole('heading',{name:'Totais de todo o recorte',exact:true}).waitFor();
      await shot(page,'extrato',width);
      await navigate(page,'Aging');
      await page.getByRole('heading',{name:'Carteira no recorte',exact:true}).waitFor();
      await shot(page,'aging',width);
      await navigate(page,'Importações');
      await page.getByRole('heading',{name:'Histórico de lotes',exact:true}).waitFor();
      await page.getByRole('button',{name:'Ver resultado',exact:true}).first().waitFor();
      await shot(page,'importacoes',width);
      await navigate(page,'Lembretes');
      await page.getByRole('heading',{name:'Nenhum lembrete encontrado',exact:true}).waitFor();
      await shot(page,'lembretes-vazio',width);
      await navigate(page,'Demonstração');
      await page.getByLabel('Nova data e hora comercial',{exact:true}).waitFor();
      await expect(page.getByRole('combobox',{name:'Título',exact:true})).toBeEnabled();
      await shot(page,'demonstracao',width);
    }
    await page.setViewportSize({width:390,height:900});
    await navigate(page,'Títulos');
    if (!(await page.getByLabel('Cliente ou título',{exact:true}).isVisible())) await page.getByRole('button',{name:'Filtrar carteira',exact:true}).click();
    await page.getByLabel('Cliente ou título',{exact:true}).fill('UIUX-SEM-RESULTADO');
    await page.getByRole('button',{name:'Filtrar títulos',exact:true}).click();
    await page.getByRole('heading',{name:'Nenhum título encontrado',exact:true}).waitFor();
    await shot(page,'vazio',390);
    if (process.env.REVIEW_FIREFOX==='true') {
      const other = await firefox.launch({headless:true});
      try { const otherPage=await other.newPage({viewport:{width:390,height:900}}); await login(otherPage,'leitor'); await navigate(otherPage,'Aging'); await otherPage.getByRole('heading',{name:'Carteira no recorte',exact:true}).waitFor(); await shot(otherPage,'firefox-aging',390); record.second_engine={engine:'firefox',version:other.version(),journey:'reader login -> aging, real application'}; } finally {await other.close();}
    }
    record.status='PASSED';
  } catch (error) { record.status='FAILED';record.failure=error.message;throw error; }
  finally { fs.writeFileSync(path.join(output,'capture.json'),JSON.stringify(record,null,2)+'\n'); await browser.close(); }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
