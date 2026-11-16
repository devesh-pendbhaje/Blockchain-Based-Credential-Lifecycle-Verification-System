import { beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { webcrypto } from 'node:crypto';
import { encryptPackage, decryptPackage, holderPackages } from '@/services/holderPackages';
import { tokenStore } from '@/services/tokenStore';

const hex = '0x' + 'ab'.repeat(32);
const pkg = {credential_id:hex, issuer_id:hex, fingerprint:hex, document_digest:hex,
  metadata_digest:hex, merkle_root:hex, version:1,
  attributes:{degree:'Computer Science', privateNote:'Fictional private value'},
  salts:{degree:hex, privateNote:hex}};
beforeAll(() => Object.defineProperty(globalThis, 'crypto', {value:webcrypto, configurable:true}));
beforeEach(() => {tokenStore.clearToken();holderPackages.clear();localStorage.clear();sessionStorage.clear();});
describe('Encrypted holder package boundaries', () => {
  it('round trips exact original salts without plaintext in the envelope', async () => {
    const text = await encryptPackage(pkg, 'example-passphrase');
    expect(text).not.toContain('Fictional private value');
    expect(text).not.toContain(hex);
    expect(await decryptPackage(text, 'example-passphrase')).toEqual(pkg);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
  it('rejects a wrong passphrase and modified ciphertext', async () => {
    const text = await encryptPackage(pkg, 'example-passphrase');
    await expect(decryptPackage(text, 'wrong-passphrase')).rejects.toThrow('Cannot unlock');
    const envelope=JSON.parse(text);
    envelope.ciphertext=(envelope.ciphertext[0]==='A'?'B':'A')+envelope.ciphertext.slice(1);
    await expect(decryptPackage(JSON.stringify(envelope), 'example-passphrase')).rejects.toThrow('Cannot unlock');
  });
  it('rejects missing original salts', async () => {
    await expect(encryptPackage({...pkg, salts:{degree:hex}}, 'example-passphrase')).rejects.toThrow('Original salts');
  });
  it('clears decrypted packages and selection on logout or identity change', () => {
    tokenStore.setToken('issuer'); holderPackages.add(pkg);
    expect(holderPackages.getSelected()).toEqual(pkg);
    tokenStore.setToken('holder');
    expect(holderPackages.getSnapshot()).toEqual([]);
    expect(holderPackages.getSelected()).toBeNull();
    holderPackages.add(pkg); tokenStore.clearToken();
    expect(holderPackages.getSnapshot()).toEqual([]);
  });
});
