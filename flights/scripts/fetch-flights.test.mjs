import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {normalize,update} from './fetch-flights.mjs';
const row={origin:'DLC',destination:'KWE',price:620,duration:220,departure_at:'2026-11-15T08:10:00+08:00',transfers:0,airline:'CZ',flight_number:'1234'};
test('normalize preserves dated cached fare, never fabricates transfer airports',()=>{
 assert.equal(normalize(row,'KWE').date,'2026-11-15');
 for(const changes of [{price:-1},{duration:0},{transfers:1},{origin:'PEK'},{departure_at:'invalid'},{airline:'<script>'}]) assert.equal(normalize({...row,...changes},'KWE'),null);
});
test('no key, empty API and failed API preserve file byte for byte',async()=>{
 const url=new URL('../flights-data.json',import.meta.url),before=await readFile(url,'utf8');
 const oldKey=process.env.FLIGHT_API_KEY,oldFetch=globalThis.fetch;
 try {
  delete process.env.FLIGHT_API_KEY;await update();assert.equal(await readFile(url,'utf8'),before);
  process.env.FLIGHT_API_KEY='test';globalThis.fetch=async()=>({ok:true,json:async()=>({success:true,data:[]})});await update();assert.equal(await readFile(url,'utf8'),before);
  globalThis.fetch=async()=>({ok:false,status:503});await update();assert.equal(process.exitCode,1);assert.equal(await readFile(url,'utf8'),before);process.exitCode=0;
 }finally{globalThis.fetch=oldFetch;if(oldKey===undefined)delete process.env.FLIGHT_API_KEY;else process.env.FLIGHT_API_KEY=oldKey;}
});
