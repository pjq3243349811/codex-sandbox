/**
 * Merge Duffel search-result JSON (the offers/slices/segments format) into page data.
 * Usage: node flights/scripts/duffel-to-data.mjs [--data path] input.json [...]
 * A fresh result replaces only its route/date groups; other groups are retained.
 * Empty searches require --origin DLC --destination THQ --date YYYY-MM-DD.
 * Empty groups live in `empty`, never as fabricated flight cards.
 */
import { readFile, writeFile, rename, unlink } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const airlines = { 'China Southern Airlines':'中国南方航空', 'China Eastern Airlines':'中国东方航空', 'Air China':'中国国际航空', 'Shandong Airlines':'山东航空', 'Hainan Airlines':'海南航空', 'Sichuan Airlines':'四川航空', 'Xiamen Airlines':'厦门航空' };
const group = f => `${f.origin}/${f.destination}/${f.date}`;
const identity = f => JSON.stringify([group(f), f.flightNumber, f.departure, f.durationMinutes, f.stops, f.cabin]);
function minutes(value) {
  const m = /^(?:(\d+)h)?(?:(\d+)m)?$/.exec(value ?? '');
  const n = m && (Number(m[1] || 0) * 60 + Number(m[2] || 0));
  if (!n) throw Error(`Invalid duration: ${value}`);
  return n;
}
function route(value) {
  if (!/^[A-Z]{3}$/.test(value.origin) || !/^[A-Z]{3}$/.test(value.destination) || !/^\d{4}-\d{2}-\d{2}$/.test(value.date) || new Date(value.date).toISOString().slice(0,10) !== value.date) throw Error('Invalid route/date');
  return value;
}
export function convert(result, emptyRoute) {
  if (result.ok !== true || !Array.isArray(result.offers)) throw Error('Expected successful Duffel result with offers array');
  if (!result.offers.length) {
    if (!emptyRoute) throw Error('Empty search needs explicit --origin, --destination and --date');
    route(emptyRoute);
    if (!result.requested_routes?.some(r => r.origin === emptyRoute.origin && r.destination === emptyRoute.destination)) throw Error('Empty route does not match requested_routes');
    if (result.search_coverage?.complete !== true) throw Error('Incomplete search cannot mark a route empty');
    return { flights: [], empty: [emptyRoute] };
  }
  const flights = result.offers.map(o => {
    if (o.currency !== 'USD' || !/^\d+(?:\.\d+)?$/.test(String(o.price)) || Number(o.price) <= 0) throw Error('Expected positive USD total price');
    if (o.passengers?.length !== 1 || o.passengers[0].type !== 'adult') throw Error('Page prices require one adult');
    if (o.slices?.length !== 1) throw Error('Page data requires one-way offers');
    const s = o.slices[0], segments = s.segments;
    if (!segments?.length) throw Error('Missing segments');
    const first = segments[0], last = segments.at(-1);
    if (first.from !== s.from || last.to !== s.to || segments.some((seg,i) => i && segments[i-1].to !== seg.from)) throw Error('Inconsistent segment route');
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(first.departing_at) || !o.airline || segments.some(seg => !seg.flight)) throw Error('Missing flight details');
    const stops = segments.slice(0,-1).map(seg => seg.to);
    if (!Number.isInteger(s.stops) || s.stops < stops.length) throw Error('Invalid stop count');
    while (stops.length < s.stops) stops.push('经停');
    const f = { origin:s.from, destination:s.to, airline:airlines[o.airline] || o.airline, flightNumber:segments.map(seg => seg.flight).join('/'), departure:first.departing_at.slice(11,16), durationMinutes:minutes(s.duration), stops, price:Math.round(Number(o.price)*7.15), priceUSD:Number(o.price), cabin:s.cabin?.toLowerCase(), date:first.departing_at.slice(0,10) };
    route(f);
    if (!f.cabin || f.origin === 'DLC' && f.destination === 'THQ') throw Error('Unsupported cabin or THQ quote; preserve empty route');
    return f;
  });
  return { flights, empty:[] };
}
export async function main(args = process.argv.slice(2)) {
  let dataPath = fileURLToPath(new URL('../flights-data.json', import.meta.url));
  const inputs = [], explicit = {};
  for (let i=0; i<args.length; i++) {
    const arg=args[i];
    if (['--data','--origin','--destination','--date'].includes(arg)) {
      const value=args[++i];
      if (!value || value.startsWith('--')) throw Error(`Missing value for ${arg}`);
      if (arg==='--data') dataPath=resolve(value); else explicit[arg.slice(2)]=value;
    } else if (arg.startsWith('--')) throw Error(`Unknown option ${arg}`);
    else inputs.push(arg);
  }
  if (!inputs.length) throw Error('Usage: duffel-to-data.mjs [--data path] input.json [...]');
  const previous = JSON.parse(await readFile(dataPath,'utf8'));
  if (!Array.isArray(previous.flights) || previous.currency !== 'CNY') throw Error('Invalid existing page data');
  const incoming = new Map(), empties = new Map();
  for (const input of inputs) {
    const converted=convert(JSON.parse(await readFile(input,'utf8')), Object.keys(explicit).length ? explicit : undefined);
    // Last input for a route/date wins; duplicate offers keep the cheapest total.
    const groups=new Map();
    for (const f of converted.flights) {
      if (!groups.has(group(f))) groups.set(group(f), new Map());
      const records=groups.get(group(f)), key=identity(f);
      if (!records.has(key) || records.get(key).priceUSD > f.priceUSD) records.set(key,f);
    }
    for (const [key, records] of groups) { incoming.set(key,[...records.values()]); empties.delete(key); }
    for (const e of converted.empty) { incoming.set(group(e),[]); empties.set(group(e),e); }
  }
  const flights=previous.flights.filter(f => !incoming.has(group(f))).concat(...incoming.values());
  const now=new Date().toISOString();
  const next={...previous, updatedAt:now, updated_at:now, flights};
  const empty=(previous.empty || []).filter(e => !incoming.has(group(e))).concat(...empties.values());
  if (previous.empty || empty.length) next.empty=empty;
  const temporary=`${dataPath}.${process.pid}.tmp`;
  try { await writeFile(temporary,JSON.stringify(next,null,2)+'\n',{flag:'wx'}); await rename(temporary,dataPath); }
  finally { await unlink(temporary).catch(() => {}); }
  console.log(JSON.stringify({updated_at:now, counts:Object.fromEntries([...new Set(flights.map(group))].map(key => [key,flights.filter(f => group(f)===key).length])), empty} ,null,2));
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode=1; });
}
