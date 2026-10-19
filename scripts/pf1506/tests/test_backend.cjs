// Exercise production backend identity/lifecycle logic with inert config/feed/ICAL doubles.
// The ICAL double supplies single events; this does not test recurrence or iCal parsing.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../kiosk/assets/web/backend.js'), 'utf8');
const id = url => 'feed-v2-' + crypto.createHash('sha256').update(url).digest('hex') + '.ics';
const A = id('https://calendar.invalid/a'), B = id('https://calendar.invalid/b'), C = id('https://calendar.invalid/chores');
const cal = (feedId, name) => ({feedId, name, color:'#123456'});
const config = (calendars, chores = false) => ({calendars, hasChores:chores,
  ...(chores ? {choresFeedId:C} : {}), kids:[{name:'Child', color:'#234567'}], units:'us'});
const raw = title => JSON.stringify({title});
function deferred() { let resolve; const promise = new Promise(r => { resolve=r; }); return {promise, resolve}; }
function fixture(initial) {
  let clock = new Date(2026, 9, 18, 12).getTime();
  class Clock extends Date { static now() { return clock; } }
  const time = hour => ({year:2026, month:10, day:18, hour, minute:0, second:0,
    isDate:false, zone:{tzid:'floating'}});
  const ICAL = {
    parse: JSON.parse,
    Component: class {
      constructor(parsed) { this.parsed = parsed; }
      getAllSubcomponents(type) {
        return type === 'vevent' ? [{title:this.parsed.title, hasProperty:()=>false,
          getFirstPropertyValue:key=>key==='uid'?this.parsed.title:null}] : [];
      }
    },
    Event: class {
      constructor(component) {
        this.component=component; this.uid=component.title; this.summary=component.title;
        this.startDate=time(8); this.endDate=time(9);
      }
      isRecurring() { return false; }
    },
    Timezone:{localTimezone:{}},
  };
  const server = {current:initial, bodies:new Map(), calls:[], reloads:0, getConfigCalls:0};
  const context=vm.createContext({Date:Clock});
  vm.runInContext(source, context);
  const backend=context.FrameBackend.create({ICAL,
    now:()=>new Date(2026,9,18,12),
    getConfig:async()=> { server.getConfigCalls++; return JSON.parse(JSON.stringify(server.current)); },
    fetchFeed:async key=> {
      assert.match(key, /^feed-v2-[0-9a-f]{64}\.ics$/, 'requests use a digest, never a slot');
      server.calls.push(key);
      const value=server.bodies.get(key);
      if (value instanceof Error || value == null) throw value || new Error('offline');
      return typeof value === 'function' ? value() : {text:value, stale:false};
    },
    fetchJson:async()=> { throw new Error('unexpected weather/network request'); },
    store:{get:()=>null,set() {}},
  });
  return {backend, server, advance(ms) { clock+=ms; },
    async saveWithFailedReply(next) {
      // Model Config.save committing before reply(c,...) throws: callback/reload never runs.
      server.current=next;
      throw new Error('HTTP reply failed after persistence');
    }};
}
const titles = data => Array.from(data.events, event=>event.title);
(async()=> {
  const f=fixture(config([cal(A,'Family')]));
  f.server.bodies.set(A,raw('Private A'));
  assert.deepEqual(titles(await f.backend.data(0)),['Private A']);
  await assert.rejects(f.saveWithFailedReply(config([cal(B,'Family')])), /after persistence/);
  f.advance(61000); // Public config refresh occurs before the normal five-minute feed refresh.
  const replaced=await f.backend.data(0);
  assert.deepEqual(titles(replaced),[], 'same-name URL-only replacement offline cannot inherit A');
  assert.equal(f.server.reloads,0);
  assert.ok(replaced.errors.some(e=>e.includes('Family:')));
  assert.equal(f.server.calls.at(-1),B);
  f.server.current=config([cal(B,'Replacement')]);
  f.advance(61000);
  assert.deepEqual(titles(await f.backend.data(0)),[], 'renaming replacement cannot relabel private A');
  console.log('PASS: persisted save with failed HTTP reply/no reload; same-name URL-only and offline replacement');

  const r=fixture(config([cal(A,'Alpha'),cal(B,'Beta')],true));
  r.server.bodies.set(A,raw('Private A')); r.server.bodies.set(B,raw('Private B'));
  r.server.bodies.set(C,raw('Child: Private chore'));
  await r.backend.data(0);
  r.server.current=config([cal(B,'Beta'),cal(A,'Alpha')],true);
  for (const key of [A,B,C]) r.server.bodies.set(key,new Error('offline'));
  r.advance(61000);
  const reordered=await r.backend.data(0);
  assert.deepEqual(Array.from(reordered.events,e=>[e.calendar,e.title]),[['Beta','Private B'],['Alpha','Private A']]);
  assert.equal(reordered.chores.kids[0].chores[0].title,'Private chore');
  r.server.current=config([cal(B,'Beta')],true); r.advance(61000);
  const removed=await r.backend.data(0);
  assert.deepEqual(titles(removed),['Private B']);
  assert.equal(removed.chores.kids[0].chores[0].title,'Private chore');
  r.server.current=config([cal(A,'Alpha'),cal(B,'Beta')],true); r.advance(61000);
  assert.deepEqual(titles(await r.backend.data(0)),['Private B'], 'removed raw cache was pruned, not revived');
  r.server.current=config([cal(B,'Beta')],true);
  r.server.current.choresFeedId=A; r.advance(61000);
  assert.deepEqual(Array.from((await r.backend.data(0)).chores.kids[0].chores),[], 'chores replacement cannot inherit another identity');
  console.log('PASS: reorder, removal/pruning, active chores retention and offline chores replacement');

  const race=fixture(config([cal(A,'Family')]));
  race.server.bodies.set(A,raw('Private A')); await race.backend.data(0);
  const waiting=deferred(), started=deferred();
  race.server.bodies.set(A,()=> { started.resolve(); return waiting.promise; });
  race.advance(301000);
  const oldResult=race.backend.data(0).then(value=>({value}),error=>({error}));
  await started.promise;
  await assert.rejects(race.saveWithFailedReply(config([cal(B,'Family')])), /after persistence/);
  race.advance(61000);
  assert.deepEqual(titles(await race.backend.data(0)),[]);
  waiting.resolve({text:raw('Late private A'),stale:false});
  const old=await oldResult;
  assert.match(old.error.message,/settings changed/);
  assert.deepEqual(titles(await race.backend.data(0)),[], 'old completion cannot repopulate current raw cache');
  assert.equal(race.server.reloads,0);
  console.log('PASS: old in-flight feed response discarded after configuration identity changes');

  const shared=fixture(config([cal(A,'Family')]));
  const hold=deferred();
  shared.server.bodies.set(A,()=>hold.promise);
  const one=shared.backend.data(0), two=shared.backend.data(1);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(shared.server.getConfigCalls,1);
  assert.equal(shared.server.calls.length,1);
  hold.resolve({text:raw('Shared refresh'),stale:false});
  await Promise.all([one,two]);
  console.log('PASS: simultaneous selected/current-week loads coalesce config and feed work');
})().catch(error=> { console.error(error); process.exitCode=1; });
