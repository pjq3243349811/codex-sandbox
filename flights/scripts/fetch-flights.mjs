/** Travelpayouts Data API cached fares; no live inventory or paid API calls. */
import { readFile, writeFile, rename } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const file = fileURLToPath(new URL('../flights-data.json', import.meta.url));
export function normalize(item, destination) {
  if (item.origin !== 'DLC' || item.destination !== destination || !Number.isFinite(item.price) || item.price <= 0 || !Number.isInteger(item.duration) || item.duration <= 0 || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(item.departure_at) || !Number.isInteger(item.transfers) || item.transfers !== 0 || !/^[A-Z0-9]{2,3}$/.test(item.airline) || !/^[A-Z0-9 -]{1,10}$/.test(String(item.flight_number))) return null;
  // API does not identify intermediate airports here: retain only verified non-stop records.
  return { origin: item.origin, destination, airline: ({CZ:'中国南方航空',CA:'中国国际航空',MU:'中国东方航空',HU:'海南航空'})[item.airline] || item.airline, flightNumber: `${item.airline}${item.flight_number}`, departure:item.departure_at.slice(11,16), date:item.departure_at.slice(0,10), durationMinutes:item.duration, stops:[], price:item.price, cabin:'economy' };
}
export async function update() {
  const key = process.env.FLIGHT_API_KEY;
  if (!key) { console.log('FLIGHT_API_KEY 未设置：安全跳过，保留现有数据（首次为示例）。'); return; }
  const date = new Date(); date.setUTCDate(date.getUTCDate()+7);
  const flights=[];
  try {
    for (const destination of ['KWE','THQ','KMG','PEK']) {
      const url = new URL('https://api.travelpayouts.com/aviasales/v3/prices_for_dates');
      url.search = new URLSearchParams({origin:'DLC',destination,departure_at:date.toISOString().slice(0,10),currency:'cny',one_way:'true',direct:'true',limit:'30',sorting:'price'});
      const response = await fetch(url, { headers: { 'X-Access-Token':key }, signal:AbortSignal.timeout(20000) });
      if (!response.ok) throw Error(`API HTTP ${response.status}`);
      const body=await response.json();
      if (!body.success || !Array.isArray(body.data)) throw Error('API 响应格式不符');
      flights.push(...body.data.map(i=>normalize(i,destination)).filter(Boolean));
    }
    if (!flights.length) { console.log('没有可用人民币直飞报价；保留原数据及其来源、更新时间。'); return; }
    const next={kind:'cached',source:'Travelpayouts / Aviasales Data API 缓存报价（非实时，可能不含全部税费）',updatedAt:new Date().toISOString(),currency:'CNY',flights};
    const previous=JSON.parse(await readFile(file,'utf8'));
    if (JSON.stringify(previous.flights)===JSON.stringify(flights) && previous.kind==='cached') {console.log('报价无变化。');return;}
    await writeFile(file+'.tmp',JSON.stringify(next,null,2)+'\n');
    await rename(file+'.tmp',file);
    console.log(`已更新 ${flights.length} 条缓存参考报价。`);
  } catch { console.error('报价更新失败；保留原数据与时间戳。请检查 API 权限、配额和服务状态。'); process.exitCode=1; }
}
if (process.argv[1] && fileURLToPath(import.meta.url)===fileURLToPath(new URL(`file://${process.argv[1]}`))) await update();
