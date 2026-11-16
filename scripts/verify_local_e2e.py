"""Exercise the running local stack through HTTP and real Hardhat contracts."""
import base64
import json
from pathlib import Path
import secrets
from urllib.parse import urlparse
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'data/local/current.json').read_text())
    base, rpc = manifest['api_url'], manifest['rpc_url']
    if any(urlparse(url).hostname != '127.0.0.1' for url in (base, rpc)):
        raise RuntimeError('Only the isolated loopback stack may be tested')
    chain = httpx.post(rpc, json={'jsonrpc':'2.0','id':1,'method':'eth_chainId','params':[]}).json()
    assert int(chain['result'], 16) == 31337
    client = httpx.Client(base_url=base, timeout=30)
    checks = []

    def request(method, path, expected=200, headers=None, **kwargs):
        response = client.request(method, '/api/v1' + path, headers=headers, **kwargs)
        assert response.status_code == expected, (path, response.status_code, response.text[:600])
        return response.json()

    def persona(role):
        token = request('POST', '/auth/dev-token', json={'persona':role})
        return {'Authorization':'Bearer ' + token['access_token']}

    issuer, holder, verifier = (persona(r) for r in ['issuer','holder','verifier'])
    upload = request('POST','/documents/upload',201,issuer,
                     files={'file':('certificate.pdf', b'%PDF-1.4\nLocal demonstration credential\n%%EOF', 'application/pdf')})
    metadata = request('POST','/documents/canonical-metadata',headers=issuer,
                       json={'metadata':{'institution':'Local Demo University','qualification':'Computer Science'}})
    attrs = {'degree':'BSc Computer Science', 'graduationYear':'2026', 'name':'Demo Student'}
    tree = request('POST','/merkle/build-tree',headers=issuer,json={'attributes':attrs})
    payload = dict(credential_id='0x'+secrets.token_hex(32),issuer_id=manifest['issuer_id'],version=1,
                   document_digest=upload['document_digest'],metadata_digest=metadata['metadata_digest'],
                   merkle_root=tree['merkle_root'],expires_at=0,idempotency_key=secrets.token_hex(16))
    issued = request('POST','/credentials',201,issuer,json=payload)
    assert issued['issuance_status'] == 'CONFIRMED' and issued['current_status'] == 'ACTIVE', issued
    fp = issued['current_fingerprint']
    checks.append('Upload, canonicalize, salt and issue: confirmed on real Hardhat')
    same = request('POST','/credentials',201,issuer,json=payload)
    assert same['issuance_tx_hash'] == issued['issuance_tx_hash']
    request('GET','/credentials',403,holder)
    assert request('GET',f'/credentials/fingerprint/{fp}/verify')['is_valid']
    checks.append('Idempotent issuance, holder isolation and public verification')

    def presentation(version, fingerprint):
        session = 'e2e-' + secrets.token_hex(8)
        challenge = request('POST','/challenges',201,verifier,
                            json={'verifier_session_id':session,'credential_fingerprint':fingerprint})
        proof = request('POST','/presentations/generate',headers=holder,json={
            'credential_id':payload['credential_id'],'issuer_id':payload['issuer_id'],'version':version,
            'document_digest':payload['document_digest'],'metadata_digest':payload['metadata_digest'],
            'attributes':attrs,'salts':tree['salts'],'disclosed_keys':['degree'],
            'challenge_id':challenge['challenge_id'],'challenge_nonce':challenge['challenge_nonce']})
        assert proof['merkle_root'] == tree['merkle_root']
        assert [c['key'] for c in proof['disclosed_claims']] == ['degree']
        return dict(presentation=proof,verifier_session_id=session,require_current_version=True)

    proof = presentation(1,fp)
    assert request('POST','/presentations/verify',headers=verifier,json=proof)['overall_valid']
    request('POST','/presentations/verify',409,verifier,json=proof)
    checks.append('Selective disclosure with original salts; replay rejected')
    path = '/credentials/' + payload['credential_id']
    suspended = request('POST',path+'/suspend',headers=issuer,json={'reason_code':1})
    assert suspended['current_status'] == 'SUSPENDED'
    assert not request('GET',f'/credentials/fingerprint/{fp}/verify')['is_valid']
    assert not request('POST','/presentations/verify',headers=verifier,json=presentation(1,fp))['overall_valid']
    active = request('POST',path+'/reactivate',headers=issuer)
    assert active['current_status'] == 'ACTIVE'
    assert request('GET',f'/credentials/fingerprint/{fp}/verify')['is_valid']
    checks.append('Suspension blocks both verification paths; reactivation restores validity')
    payload.update(version=2,idempotency_key=secrets.token_hex(16))
    second = request('POST','/credentials',201,issuer,json=payload)
    assert second['current_version'] == 2 and second['issuance_status'] == 'CONFIRMED'
    assert not request('GET',f'/credentials/fingerprint/{fp}/verify')['is_valid']
    fp2 = second['current_fingerprint']
    assert request('POST','/presentations/verify',headers=verifier,json=presentation(2,fp2))['overall_valid']
    revoked = request('POST',path+'/revoke',headers=issuer,json={'reason_code':1})
    assert revoked['current_status'] == 'REVOKED'
    assert not request('GET',f'/credentials/fingerprint/{fp2}/verify')['is_valid']
    request('POST',path+'/reactivate',400,issuer)
    checks.append('Real supersession invalidates old version; revocation is terminal')

    # Leave a usable, fictional active credential and encrypted holder package.
    payload.update(credential_id='0x'+secrets.token_hex(32),version=1,idempotency_key=secrets.token_hex(16))
    demo = request('POST','/credentials',201,issuer,json=payload)
    package = {k:payload[k] for k in ['credential_id','issuer_id','version','document_digest','metadata_digest','merkle_root','expires_at']}
    package.update(fingerprint=demo['current_fingerprint'], attributes=attrs, salts=tree['salts'])
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    salt, iv = secrets.token_bytes(16), secrets.token_bytes(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=310000).derive(b'local-demo-passphrase')
    ciphertext = AESGCM(key).encrypt(iv,json.dumps(package).encode(),b'credential-holder-package:v1')
    encode = lambda b: base64.b64encode(b).decode()
    envelope = dict(format='credential-package',version=1,iterations=310000,
                    salt=encode(salt),iv=encode(iv),ciphertext=encode(ciphertext))
    run_dir = Path(manifest['run_dir'])
    (run_dir / 'demo-holder.credential').write_text(json.dumps(envelope))
    result = dict(checks=checks, demo_credential_id=payload['credential_id'], demo_fingerprint=demo['current_fingerprint'],
                  package=str(run_dir / 'demo-holder.credential'), issuer_id=payload['issuer_id'])
    (run_dir / 'e2e-result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    client.close()


if __name__ == '__main__':
    main()
