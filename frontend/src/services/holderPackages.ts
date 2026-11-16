import { z } from 'zod';
import { CredentialPackage } from '@/types/credential';
import { tokenStore } from './tokenStore';
const hex = z.string().regex(/^0x[0-9a-fA-F]{64}$/);
const schema = z.object({credential_id:hex, issuer_id:hex, fingerprint:hex, document_digest:hex,
  metadata_digest:hex, merkle_root:hex, version:z.number().int().min(1).max(4294967295),
  attributes:z.record(z.string().min(1).max(128),z.string().max(2048)), salts:z.record(hex),
  created_at:z.string().optional(), expires_at:z.number().optional()}).strict();
export function validatePackage(value: unknown): CredentialPackage {
  const pkg=schema.parse(value), keys=Object.keys(pkg.attributes);
  if (!keys.length || keys.length>100 || keys.some(k=>['__proto__','constructor','prototype'].includes(k)) ||
      keys.length!==Object.keys(pkg.salts).length || keys.some(k=>!pkg.salts[k])) throw new Error('Original salts are required for every attribute.');
  return pkg;
}
let packages: CredentialPackage[]=[];
let selected: string|null=null;
const listeners=new Set<()=>void>();
export const holderPackages={
  subscribe(fn:()=>void){listeners.add(fn);return ()=>{listeners.delete(fn);};},
  getSnapshot:()=>packages,
  getSelected:()=>packages.find(p=>p.fingerprint===selected)||null,
  select(fp:string){selected=fp;},
  add(value:unknown){const pkg=validatePackage(value);packages=[...packages.filter(p=>p.fingerprint!==pkg.fingerprint),pkg];selected=pkg.fingerprint;listeners.forEach(fn=>fn());},
  clear(){packages=[];selected=null;listeners.forEach(fn=>fn());}
};
let previousToken=tokenStore.getToken();
tokenStore.subscribe(token=>{if(token!==previousToken)holderPackages.clear();previousToken=token;});
const iterations=310000;
const aad=new TextEncoder().encode('credential-holder-package:v1');
function base64(b:Uint8Array){return btoa(Array.from(b,c=>String.fromCharCode(c)).join(''));}
function decode(v:string){return Uint8Array.from(atob(v),c=>c.charCodeAt(0));}
async function key(passphrase:string,salt:Uint8Array){
  if(passphrase.length<12)throw new Error('Use a passphrase of at least 12 characters.');
  const material=await crypto.subtle.importKey('raw',new TextEncoder().encode(passphrase),'PBKDF2',false,['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2',salt:new Uint8Array(salt),iterations,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
}
export async function encryptPackage(pkg:CredentialPackage,passphrase:string):Promise<string>{
  const salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12));
  const plaintext=new TextEncoder().encode(JSON.stringify(validatePackage(pkg)));
  const ciphertext=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:aad},await key(passphrase,salt),plaintext);
  return JSON.stringify({format:'credential-package',version:1,iterations,salt:base64(salt),iv:base64(iv),ciphertext:base64(new Uint8Array(ciphertext))});
}
export async function decryptPackage(text:string,passphrase:string):Promise<CredentialPackage>{
  if(text.length>1000000)throw new Error('Package exceeds 1 MB.');
  try{
    const e=JSON.parse(text);
    if(e.format!=='credential-package'||e.version!==1||e.iterations!==iterations)throw new Error();
    const salt=decode(e.salt),iv=decode(e.iv);
    if(salt.length!==16||iv.length!==12)throw new Error();
    const bytes=await crypto.subtle.decrypt({name:'AES-GCM',iv,additionalData:aad},await key(passphrase,salt),decode(e.ciphertext));
    return validatePackage(JSON.parse(new TextDecoder().decode(bytes)));
  }catch{throw new Error('Cannot unlock package: wrong passphrase, damaged file, or unsupported format.');}
}
export function downloadText(text:string,filename:string){
  const url=URL.createObjectURL(new Blob([text],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
