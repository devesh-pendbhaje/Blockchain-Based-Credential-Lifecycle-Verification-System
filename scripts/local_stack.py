"""Run an isolated local chain + SQLite database + API + UI. No public RPC access.

Each start creates a new local chain session; previous databases and encrypted
files are retained in data/local. Stop only signals this launcher's own session.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'data' / 'local'
MANIFEST = LOCAL / 'current.json'
ISSUER_ID = '0x' + '0' * 63 + '1'


def read_manifest():
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else None


def status():
    manifest = read_manifest()
    if not manifest:
        print('No local session has been started.')
        return
    try:
        with urlopen(manifest['api_url'] + '/health/ready', timeout=3) as response:
            health = json.load(response)
        print(json.dumps({'frontend': manifest['frontend_url'], 'health': health, 'session': manifest['run_dir']}, indent=2))
    except Exception:
        print('Local session is stopped or not ready. Logs: ' + manifest['run_dir'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['start', 'stop', 'status'], nargs='?', default='start')
    parser.add_argument('--api-port', type=int, default=8000)
    parser.add_argument('--ui-port', type=int, default=5173)
    parser.add_argument('--rpc-port', type=int, default=8545)
    args = parser.parse_args()
    if args.command == 'status':
        return status()
    if args.command == 'stop':
        manifest = read_manifest()
        if manifest:
            (Path(manifest['run_dir']) / 'stop').touch()
            print('Stop requested for the local session.')
        return
    for port in (args.rpc_port, args.api_port, args.ui_port):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                raise SystemExit(f'Port {port} is in use. Stop the existing service or choose another port.')
    run_dir = LOCAL / (time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
    run_dir.mkdir(parents=True)
    rpc = f'http://127.0.0.1:{args.rpc_port}'
    api = f'http://127.0.0.1:{args.api_port}'
    ui = f'http://127.0.0.1:{args.ui_port}'
    env = os.environ.copy()
    # Explicit values supersede any existing root .env without modifying it.
    env.update(ENVIRONMENT='development', AUTH_MODE='local_dev',
        DATABASE_URL='sqlite:///' + (run_dir / 'credentials.sqlite3').as_posix(),
        BLOCKCHAIN_RPC_URL=rpc, BLOCKCHAIN_CHAIN_ID='31337', CHAIN_ID='31337',
        BLOCKCHAIN_SIGNER_PRIVATE_KEY='', BLOCKCHAIN_ISSUER_PRIVATE_KEYS='{}', ISSUER_REGISTRY_ADDRESS='', CREDENTIAL_REGISTRY_ADDRESS='',
        BLOCKCHAIN_TIMEOUT_SECONDS='10', CONFIRMATION_BLOCKS='1',
        STORAGE_ROOT_DIR=str(run_dir / 'storage'), STORAGE_ENCRYPTION_KEY=secrets.token_hex(32),
        STORAGE_PREVIOUS_ENCRYPTION_KEYS='[]', AUTH_DEV_PRIVATE_KEY='', AUTH_DEV_PUBLIC_KEY='',
        OIDC_ISSUER_URL='https://local.credentials.test', OIDC_AUDIENCE='credential-local',
        OIDC_JWKS_URL='', VITE_API_BASE_URL=api,
        CORS_ORIGINS=json.dumps([ui, f'http://localhost:{args.ui_port}']))
    env['PYTHONPATH'] = str(ROOT / 'backend')
    children = []
    logs = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

    def spawn(command, cwd, name):
        log = open(run_dir / (name + '.log'), 'w', encoding='utf-8')
        logs.append(log)
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=flags)
        children.append(process)
        return process

    def wait_for(check, label, timeout=50):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in children):
                raise RuntimeError(f'A service exited while waiting for {label}. Logs: {run_dir}')
            try:
                if check():
                    return
            except Exception:
                pass
            time.sleep(.4)
        raise RuntimeError(f'Timed out waiting for {label}. Logs: {run_dir}')

    try:
        hardhat = ROOT / 'contracts/node_modules/hardhat/internal/cli/cli.js'
        subprocess.run(['node', str(hardhat), '--config', 'hardhat.local.config.ts', 'compile'],
                       cwd=ROOT / 'contracts', env=env, check=True, creationflags=flags)
        spawn(['node', str(hardhat), '--config', 'hardhat.local.config.ts', 'node',
               '--hostname', '127.0.0.1', '--port', str(args.rpc_port)], ROOT / 'contracts', 'chain')
        from web3 import Web3
        from eth_account import Account
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 2}))
        wait_for(w3.is_connected, 'local Hardhat')
        if w3.eth.chain_id != 31337 or 'hardhat' not in w3.client_version.lower():
            raise RuntimeError('Refusing to deploy: expected local Hardhat chain 31337')
        Account.enable_unaudited_hdwallet_features()
        # Public Hardhat test mnemonic, usable only for this disposable local chain.
        signer = Account.from_mnemonic('test test test test test test test test test test test junk')
        if signer.address != w3.eth.accounts[0]:
            raise RuntimeError('Unexpected local Hardhat account')
        env['BLOCKCHAIN_SIGNER_PRIVATE_KEY'] = signer.key.hex()

        def deploy(name, *constructor_args):
            artifact = json.loads((ROOT / f'contracts/artifacts/contracts/{name}.sol/{name}.json').read_text())
            factory = w3.eth.contract(abi=artifact['abi'], bytecode=artifact['bytecode'])
            tx = factory.constructor(*constructor_args).transact({'from': signer.address})
            receipt = w3.eth.wait_for_transaction_receipt(tx)
            if receipt.status != 1:
                raise RuntimeError('Local deployment failed')
            return w3.eth.contract(address=receipt.contractAddress, abi=artifact['abi'])

        issuer_registry = deploy('IssuerRegistry', signer.address)
        credential_registry = deploy('CredentialRegistry', issuer_registry.address)
        tx = issuer_registry.functions.registerIssuer(bytes.fromhex(ISSUER_ID[2:]), signer.address, '').transact({'from': signer.address})
        if w3.eth.wait_for_transaction_receipt(tx).status != 1:
            raise RuntimeError('Local issuer registration failed')
        env['ISSUER_REGISTRY_ADDRESS'] = issuer_registry.address
        env['CREDENTIAL_REGISTRY_ADDRESS'] = credential_registry.address
        # This private local config is ignored by Git. Retain it with encrypted data.
        (run_dir / 'environment.json').write_text(json.dumps({k: env[k] for k in env if k in {
            'ENVIRONMENT', 'AUTH_MODE', 'DATABASE_URL', 'BLOCKCHAIN_RPC_URL', 'BLOCKCHAIN_CHAIN_ID',
            'CHAIN_ID', 'BLOCKCHAIN_SIGNER_PRIVATE_KEY', 'ISSUER_REGISTRY_ADDRESS', 'CREDENTIAL_REGISTRY_ADDRESS',
            'STORAGE_ROOT_DIR', 'STORAGE_ENCRYPTION_KEY', 'STORAGE_PREVIOUS_ENCRYPTION_KEYS',
            'AUTH_DEV_PRIVATE_KEY', 'AUTH_DEV_PUBLIC_KEY', 'OIDC_ISSUER_URL', 'OIDC_AUDIENCE', 'OIDC_JWKS_URL'
        }}))
        os.environ.update(env)
        sys.path.insert(0, str(ROOT / 'backend'))
        from app.db.base import Base
        from app.db.session import engine, SessionLocal
        import app.models
        from app.models.issuer import Issuer
        # Fresh SQLite session only. Existing deployments must use Alembic migrations.
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            db.add(Issuer(issuer_id=ISSUER_ID, display_name='Local Demo University', status='ACTIVE'))
            db.commit()
        spawn([sys.executable, '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend',
               '--host', '127.0.0.1', '--port', str(args.api_port)], ROOT, 'backend')
        wait_for(lambda: urlopen(api + '/health/ready', timeout=2).status == 200, 'API')
        vite = ROOT / 'frontend/node_modules/vite/bin/vite.js'
        spawn(['node', str(vite), '--host', '127.0.0.1', '--port', str(args.ui_port), '--strictPort'], ROOT / 'frontend', 'frontend')
        wait_for(lambda: urlopen(ui, timeout=2).status == 200, 'frontend')
        manifest = dict(run_dir=str(run_dir), api_url=api, frontend_url=ui, rpc_url=rpc,
                        issuer_id=ISSUER_ID, issuer_registry=issuer_registry.address,
                        credential_registry=credential_registry.address, pid=os.getpid())
        MANIFEST.write_text(json.dumps(manifest, indent=2))
        print(f'READY: {ui}\nAPI: {api}/api/v1/docs\nLocal issuer: {ISSUER_ID}\nLogs: {run_dir}', flush=True)
        while not (run_dir / 'stop').exists():
            if any(p.poll() is not None for p in children):
                raise RuntimeError('A local service stopped. Inspect session logs.')
            time.sleep(1)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    child.kill()
        for log in logs:
            log.close()


if __name__ == '__main__':
    main()
