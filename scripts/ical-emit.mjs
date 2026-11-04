import fs from 'node:fs';

const events = JSON.parse(fs.readFileSync('/tmp/ical-out.json', 'utf8'));

function esc(s) {
  return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function peopleLit(people) {
  if (people.length === 4) return 'ALL';
  return '[' + people.map((p) => `'${p}'`).join(', ') + ']';
}

const lines = [];
for (const e of events) {
  const peopleLit_ = peopleLit(e.people);
  const extra = e.loc ? `, { loc: '${esc(e.loc.split('\n')[0])}' }` : '';
  if (e.kind === 'allDay') {
    lines.push(`  icalEvents.push(allDay(${e.d}, ${e.days}, '${esc(e.title)}', ${peopleLit_}${extra}));`);
  } else {
    lines.push(`  icalEvents.push(ev(${e.d}, '${e.s}', '${e.e}', '${esc(e.title)}', ${peopleLit_}${extra}));`);
  }
}

fs.writeFileSync('/tmp/ical-emit.js', lines.join('\n') + '\n');
console.log('wrote', lines.length, 'lines -> /tmp/ical-emit.js');
