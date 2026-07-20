export const POSITIONS=['PG','SG','SF','PF','C'];
export const clamp=(value,min,max)=>Math.min(max,Math.max(min,value));
export const slugify=value=>String(value).toLowerCase().trim().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'team';
export const ordinal=n=>`${n}${n%100>=11&&n%100<=13?'th':{1:'st',2:'nd',3:'rd'}[n%10]||'th'}`;
export const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export function makeId(base,used){let id=base,index=2;while(used.has(id))id=`${base}-${index++}`;used.add(id);return id}
export function average(values){const valid=values.filter(Number.isFinite);return valid.length?valid.reduce((a,b)=>a+b,0)/valid.length:0}
export function formatSigned(value,digits=0){const number=Number(value);return`${number>0?'+':''}${number.toFixed(digits)}`}
export function escapeHTML(value){return String(value).replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]))}
