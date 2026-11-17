# Multi-university issuance: result and demo guide

## Problem and fix

Previously every credential transaction used the launcher's default signing key. The blockchain binds that address to issuer `0001`, so a request for `0002` correctly failed with `SIGNER_UNAUTHORIZED_FOR_ISSUER`. Creating a database profile alone does not register a blockchain signing authority.

The backend now selects a signing account using the credential's issuer ID. A request-scoped client preserves the governance account and prevents concurrent requests from switching the shared signer. The contract's issuer authorization and the API's tenant checks remain enforced.

Admins can activate another university on the local Hardhat chain. Activation creates a separate account, encrypts its private key in `STORAGE_ROOT_DIR/issuer-signers.json.enc`, supplies local test ETH, registers its public address through governance, and checks the resulting on-chain registration. Repeating activation reuses the same identity. Private keys are not returned to the browser.

## Show another university in the demo

1. Open the running updated demo at `http://127.0.0.1:5174` and sign in as Admin. The older app at port 5173 was left running and has not been upgraded in memory.
2. Open Issuers and create an ACTIVE profile named `Second University`. Use this unique issuer ID (or inspect its existing profile if already created):

   `0x0000000000000000000000000000000000000000000000000000000000000002`

3. In the profile details, click **Activate local university**. Wait for **University ready to issue** and an active on-chain status.
4. Click **Issue credential for this university**. The wizard fills in this issuer ID. Keep the newly generated Credential ID; do not reuse a credential previously associated with another university.
5. Complete the document, metadata, and claims steps, then issue. Inspect the resulting credential and test public verification.
6. To demonstrate university-specific access, sign out, enter the full university ID in **University Issuer ID (local demo)**, then choose the Issuer persona. Leaving the field blank selects the original demo university. This persona selector is a development feature, not production authentication.
7. Inspect the credential to suspend/reactivate it. For an update, reuse its Credential ID and the same university ID. Use permanent revocation only for a disposable demo credential.

Each separate university must have a unique issuer ID. Many credentials can belong to one university, but changing the issuer ID does not transfer an existing credential to another university.

## Verification results (2026-11-17)

The live `scripts/verify_multi_issuer.py` integration check passed on local chain 31337 with two newly created universities. It checked:

- Different signing addresses, with actual transaction senders matching each university.
- Repeat activation keeping the same address.
- Issuer and Admin credential issuance, confirmed transactions, and valid public verification.
- Suspension and reactivation; version 2 issuance and permanent revocation.
- Cross-university issuance and lifecycle mutations rejected by the API.

The original university's full `scripts/verify_local_e2e.py` demo also passed, covering its document workflow. The multi-university script uses synthetic digests to isolate signing and lifecycle behavior. Machine-readable results are stored in the active local session as `multi-issuer-result.json` and `e2e-result.json`; these generated session files are not committed.

Backend regression checks passed (123 tests). Frontend regression checks passed (39 tests), followed by the TypeScript and Vite production build. A test used an unsupported Testing Library option; it was corrected to an exact regular expression before the successful build.

## Deployment and storage boundaries

Automatic activation is restricted to Admin access in local development, a loopback RPC, Hardhat chain 31337, and the registry's governance owner. It does not create or fund accounts on public networks.

For an external deployment, provision distinct signing keys securely, configure `BLOCKCHAIN_ISSUER_PRIVATE_KEYS` as a JSON object mapping full issuer IDs to their private keys, register the corresponding public addresses through governance, and fund them for that network. The default key remains the fallback for the original issuer. Local encrypted accounts are not loaded in production. Never commit populated key configuration.

Retain the storage directory, its matching `STORAGE_ENCRYPTION_KEY`, and the chain configuration when restarting a backend against the same chain. The encrypted keystore is bound to the chain ID and registry address. A fresh local launcher session creates a fresh chain and storage directory; activate universities again in that session. Continue running a single signing backend worker: the transaction and provisioning locks are in-process, not distributed locks.

No database schema migration or smart-contract authorization bypass is required.
