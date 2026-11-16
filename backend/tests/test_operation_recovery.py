"""Fault injection: do not promote pending versions or resend uncertain transactions."""
from app.blockchain.client import blockchain_client
from app.models.issuer import Issuer
from app.models.chain_operation import ChainOperation


def seed(client, db_session, issuer_headers):
    iid = '0x' + '11' * 32
    db_session.add(Issuer(issuer_id=iid, display_name='Recovery Test', status='ACTIVE'))
    db_session.commit()
    request = dict(credential_id='0x'+'ab'*32, issuer_id=iid, version=1,
                   document_digest='0x'+'12'*32, metadata_digest='0x'+'34'*32, merkle_root='0x'+'56'*32)
    response=client.post('/api/v1/credentials', json=request, headers=issuer_headers)
    assert response.status_code == 201
    assert response.json()['issuance_status'] == 'CONFIRMED'
    return request, response.json()


def test_pending_supersession_preserves_current_and_reconciles_once(client, db_session, issuer_headers, fake_chain, monkeypatch):
    request, old=seed(client, db_session, issuer_headers)
    original=blockchain_client.supersede_credential_on_chain
    calls=[]
    def delayed(**kw):
        calls.append(kw)
        result=original(**kw)
        return dict(result, status='PENDING')
    monkeypatch.setattr(blockchain_client, 'supersede_credential_on_chain', delayed)
    request.update(version=2, merkle_root='0x'+'78'*32)
    response=client.post('/api/v1/credentials', json=request, headers=issuer_headers).json()
    assert response['current_version'] == 1
    assert response['current_fingerprint'] == old['current_fingerprint']
    assert response['pending_version'] == 2
    assert response['operation_status'] == 'SUBMITTED'
    endpoint=f"/api/v1/credentials/{request['credential_id']}/versions/2/anchor"
    monkeypatch.setattr(blockchain_client, 'get_transaction_receipt', lambda _: None)
    pending=client.post(endpoint, headers=issuer_headers)
    assert pending.status_code == 200
    assert pending.json()['current_version'] == 1
    monkeypatch.setattr(blockchain_client, 'get_transaction_receipt', lambda _: {'status':'CONFIRMED', 'block_number':42})
    done=client.post(endpoint, headers=issuer_headers)
    assert done.status_code == 200
    assert done.json()['current_version'] == 2
    assert done.json()['issuance_status'] == 'CONFIRMED'
    assert len(calls) == 1


def test_pending_lifecycle_retains_status_and_uses_persisted_hash(client, db_session, issuer_headers, fake_chain, monkeypatch):
    request, issued=seed(client, db_session, issuer_headers)
    calls=[]
    tx_hash='0x'+'90'*32
    def uncertain(**kw):
        calls.append(kw)
        kw['on_broadcast'](tx_hash)
        return {'status':'PENDING', 'tx_hash':tx_hash}
    monkeypatch.setattr(blockchain_client, 'suspend_credential_on_chain', uncertain)
    endpoint=f"/api/v1/credentials/{request['credential_id']}/suspend"
    pending=client.post(endpoint,json={'reason_code':1},headers=issuer_headers)
    assert pending.json()['current_status'] == 'ACTIVE'
    assert pending.json()['operation_tx_hash'] == tx_hash
    persisted=db_session.query(ChainOperation).filter_by(tx_hash=tx_hash).one()
    assert persisted.status == 'SUBMITTED'
    monkeypatch.setattr(blockchain_client, 'get_transaction_receipt', lambda _: None)
    retry=client.post(endpoint,json={'reason_code':1},headers=issuer_headers)
    assert retry.json()['operation_status'] == 'SUBMITTED'
    fake_chain[issued['current_fingerprint']]['status']='SUSPENDED'
    monkeypatch.setattr(blockchain_client, 'get_transaction_receipt', lambda _: {'status':'CONFIRMED'})
    done=client.post(endpoint,json={'reason_code':1},headers=issuer_headers)
    assert done.json()['current_status'] == 'SUSPENDED'
    assert done.json()['operation_status'] == 'CONFIRMED'
    assert len(calls) == 1
