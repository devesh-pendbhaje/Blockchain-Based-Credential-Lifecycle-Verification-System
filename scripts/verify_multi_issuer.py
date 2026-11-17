"""Verify real local multi-university onboarding, issuance and ownership boundaries."""
import json
import secrets
from pathlib import Path
from urllib.parse import urlparse
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'data/local/current.json').read_text())
    assert urlparse(manifest['rpc_url']).hostname == '127.0.0.1'
    assert int(httpx.post(manifest['rpc_url'], json={'jsonrpc':'2.0','id':1,'method':'eth_chainId','params':[]}).json()['result'], 16) == 31337
    with httpx.Client(base_url=manifest['api_url'] + '/api/v1', timeout=40) as api:
        def token(role, **extra):
            response = api.post('/auth/dev-token', json={'persona':role, **extra})
            response.raise_for_status()
            return {'Authorization':'Bearer ' + response.json()['access_token']}
        admin = token('admin')
        results = []
        for name in ['North Demo University', 'South Demo University']:
            issuer = '0x' + secrets.token_hex(32)
            profile = api.post('/issuers', headers=admin, json={'issuer_id':issuer,'display_name':name,'status':'ACTIVE'})
            assert profile.status_code == 201, profile.text
            activation = api.post(f'/issuers/{issuer}/activate-local', headers=admin)
            assert activation.status_code == 200, activation.text
            again = api.post(f'/issuers/{issuer}/activate-local', headers=admin)
            assert again.status_code == 200 and again.json()['already_registered']
            assert again.json()['signing_address'] == activation.json()['signing_address']
            headers = token('issuer', issuer_id=issuer)
            payload = {'issuer_id':issuer,'credential_id':'0x'+secrets.token_hex(32),'version':1,
                       'document_digest':'0x'+'11'*32,'metadata_digest':'0x'+'22'*32,'merkle_root':'0x'+'33'*32}
            issue = api.post('/credentials', headers=headers, json=payload)
            assert issue.status_code == 201, issue.text
            record = issue.json()
            assert record['issuance_status'] == 'CONFIRMED' and record['current_status'] == 'ACTIVE'
            transaction = httpx.post(manifest['rpc_url'],json={'jsonrpc':'2.0','id':2,
                'method':'eth_getTransactionByHash','params':[record['issuance_tx_hash']]}).json()['result']
            assert transaction['from'].lower() == activation.json()['signing_address'].lower()
            assert api.get(f"/credentials/fingerprint/{record['current_fingerprint']}/verify").json()['is_valid']
            if results:
                previous = results[0]
                denied = api.post(f"/credentials/{previous['credential_id']}/suspend", headers=headers, json={'reason_code':1})
                assert denied.status_code == 403
                denied_issue = api.post('/credentials', headers=headers, json=dict(payload,
                    issuer_id=previous['issuer_id'], credential_id='0x'+secrets.token_hex(32)))
                assert denied_issue.status_code == 403
            path = '/credentials/' + record['credential_id']
            assert api.post(path+'/suspend',headers=headers,json={'reason_code':1}).json()['current_status'] == 'SUSPENDED'
            assert api.post(path+'/reactivate',headers=headers).json()['current_status'] == 'ACTIVE'
            # Admin issuance also routes by requested university rather than governance address.
            payload.update(credential_id='0x'+secrets.token_hex(32))
            admin_issue = api.post('/credentials',headers=admin,json=payload)
            assert admin_issue.status_code == 201 and admin_issue.json()['issuance_status'] == 'CONFIRMED', admin_issue.text
            payload.update(version=2)
            replacement = api.post('/credentials',headers=headers,json=payload)
            assert replacement.status_code == 201 and replacement.json()['current_version'] == 2, replacement.text
            revoked = api.post('/credentials/'+payload['credential_id']+'/revoke',headers=headers,json={'reason_code':1})
            assert revoked.status_code == 200 and revoked.json()['current_status'] == 'REVOKED'
            results.append({'name':name,'issuer_id':issuer,'signing_address':activation.json()['signing_address'],
                            'credential_id':record['credential_id'],'fingerprint':record['current_fingerprint']})
        assert results[0]['signing_address'] != results[1]['signing_address']
        result = {'status':'PASS','checks':['distinct signers','idempotent activation','issuer and admin issuance',
                  'transaction sender matches university signer','public verification','suspension/reactivation',
                  'version replacement and revocation','cross-university issuance and mutation denied'], 'universities':results}
        (Path(manifest['run_dir'])/'multi-issuer-result.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
