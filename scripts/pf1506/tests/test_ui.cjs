// Host-only VM/DOM fixtures: no server, browser account, network, or calendar secrets.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const web = path.join(__dirname, '../kiosk/assets/web');
class Element {
  constructor() {
    this.style = {}; this.dataset = {}; this.textContent = ''; this.value = '';
    this.scrollHeight = 0; this.clientHeight = 500; this.children = [];
    this.classList = { contains: () => false, add() {}, remove() {}, toggle() {} };
  }
  set innerHTML(s) { this.html = s; }
  get innerHTML() { return this.html || ''; }
  querySelectorAll(selector) {
    if (selector === '.tItem') return [...this.innerHTML.matchAll(/class="tItem[^>]+/g)].map(() => new Element());
    return [];
  }
  querySelector(selector) { return selector === '.more' ? null : new Element(); }
  insertAdjacentHTML(_, html) { this.html += html; }
  addEventListener() {}
}
function fixture(file, backend = {}) {
  const html = fs.readFileSync(path.join(web, file), 'utf8');
  const elements = new Map(), handlers = {};
  const document = {
    querySelector(s) { if (!elements.has(s)) elements.set(s, new Element()); return elements.get(s); },
    querySelectorAll: () => [],
    addEventListener(name, fn) { handlers[name] = fn; },
  };
  const context = vm.createContext({ document, console, Intl, Date, setInterval() {},
    FrameBackend: { create: () => backend }, localStorage: {}, location: { reload() {} },
    fetch() { throw new Error('Unexpected network request'); } });
  const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(x => x[1]).filter(Boolean);
  let source = scripts.join('\n');
  if (file === 'index.html') source = source.replace(/renderClock\(\);\s*load\(\);\s*$/, '');
  vm.runInContext(source, context, { filename: file });
  return { html, context, elements, handlers, get: s => document.querySelector(s), run: s => vm.runInContext(s, context) };
}
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve=a; reject=b; }); return {promise, resolve, reject}; }
function data(title, day = new Date()) {
  const start = new Date(day); start.setHours(8, 0, 0, 0);
  const end = new Date(day); end.setHours(9, 0, 0, 0);
  const first = new Date(day); first.setDate(first.getDate() - first.getDay());
  return {events: [{title, start:start.toISOString(), end:end.toISOString(), calendar:'Family'}],
    calendars:{Family:{color:'#123456'}}, weather:null, errors:[], weekStart:first.toISOString().slice(0,10), hasChores:false};
}
(async () => {
  const requests=[];
  const f = fixture('index.html', {data(week) { const d=deferred(); requests.push({week,...d}); return d.promise; }});
  f.context.today = data('Today event');
  f.context.other = data('Another week event');
  f.run('state.todayData=today; state.data=other; state.week=1; renderToday();');
  assert.match(f.get('#todayList').innerHTML, /Today event/);
  assert.match(f.get('#todayList').innerHTML, /data-source="today"/);
  assert.doesNotMatch(f.get('#todayList').innerHTML, /Another week event/);
  function click(selector, dataset) {
    const hit={dataset};
    f.handlers.click({target:{closest: s => s===selector?hit:null}});
  }
  click('[data-ev]', {ev:'0', source:'today'});
  assert.match(f.get('#card').innerHTML, /Today event/);
  f.run('state.todayData={...today, events:Array(10).fill(today.events[0])}; renderToday();');
  assert.match(f.get('#todayList').innerHTML, /data-day="[^"]+" data-source="today"/);
  click('[data-day]', {day:f.run('ymd(new Date())'), source:'today'});
  assert.match(f.get('#card').innerHTML, /Today event/);
  assert.doesNotMatch(f.get('#card').innerHTML, /Another week event/);
  f.run('state.todayData=other; state.data=other;');
  click('[data-ev]', {ev:'0', source:'modal'});
  assert.match(f.get('#card').innerHTML, /Today event/, 'open day popup keeps its own dataset');
  const old=f.run('state.week=0; load()');
  const latest=f.run('state.week=1; load()');
  requests[1].resolve(data('Latest week'));
  requests[2].resolve(data('Current week'));
  await latest;
  requests[0].resolve(data('Stale response'));
  await old;
  assert.equal(f.run('state.data.events[0].title'), 'Latest week');
  const bad=f.run('state.week=2; load()');
  const fresh=f.run('state.week=3; load()');
  requests[5].resolve(data('Newest week'));
  requests[6].resolve(data('Fresh current week')); await fresh;
  requests[3].reject(new Error('Stale error'));
  requests[4].resolve(data('Stale current week')); await bad;
  assert.doesNotMatch(f.get('#banner').textContent, /Stale error/);
  console.log('PASS: Today event, Today more/day popup, popup identity, out-of-order success/error responses');

  // Start from an actually empty state, not the seeded Today state above.
  const startupRequests=[];
  const startup=fixture('index.html', {data(week) {
    const d=deferred(); startupRequests.push({week,...d}); return d.promise;
  }});
  assert.equal(startup.run('state.data'),null);
  assert.equal(startup.run('state.todayData'),undefined);
  const initial=startup.run('load()');
  const navigated=startup.run('state.week=1; load()');
  assert.deepEqual(startupRequests.map(r=>r.week),[0,1,0]);
  startupRequests[1].resolve(data('Future week only'));
  await Promise.resolve();
  assert.equal(startup.run('state.todayData'),undefined);
  startupRequests[0].resolve(data('Discarded initial current week')); await initial;
  assert.equal(startup.run('state.todayData'),undefined);
  startupRequests[2].resolve(data('Actual current week')); await navigated;
  assert.equal(startup.run('state.data.events[0].title'),'Future week only');
  assert.equal(startup.run('state.todayData.events[0].title'),'Actual current week');
  assert.match(startup.get('#todayList').innerHTML,/Actual current week/);
  assert.doesNotMatch(startup.get('#todayList').innerHTML,/Future week only|Discarded initial/);
  console.log('PASS: empty-state load0, rapid week1 navigation, response1 before response0 keeps independent Today data');

  const setup=fixture('setup.html');
  // Parse the actual HTML nesting, rather than assuming the status element is visible.
  const stack=[]; let statusAncestors;
  for (const tag of setup.html.split('<script>')[0].matchAll(/<\/?([a-z0-9]+)\b([^>]*)>/gi)) {
    const [full,name,attrs]=tag;
    if (full.startsWith('</')) { stack.pop(); continue; }
    if (/\bid="status"/.test(attrs)) statusAncestors=stack.map(x=>x.id);
    if (!['input','meta','br','link','hr'].includes(name)) stack.push({name,id:(attrs.match(/\bid="([^"]+)"/)||[])[1]});
  }
  assert.ok(statusAncestors && !statusAncestors.includes('form'), 'status is outside hidden form');
  assert.match(setup.html, /id="status" role="status" aria-live="polite"/);
  setup.context.fetch=async () => ({ok:false,text:async()=> 'wrong PIN (0 tries left before the page closes)'});
  setup.get('#pin').value='000000';
  await setup.get('#unlock').onclick();
  assert.match(setup.get('#status').textContent, /wrong PIN \(0 tries left/);
  assert.equal(setup.get('#status').className, 'bad');
  assert.notEqual(setup.get('#form').style.display, 'block');
  console.log('PASS: wrong-PIN/lockout status remains visible with settings form hidden');
})().catch(e=> {console.error(e);process.exitCode=1;});
