import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { IssuersPage } from '@/pages/IssuersPage';
import { CredentialIssuancePage } from '@/pages/CredentialIssuancePage';
import { issuerApi } from '@/services/issuerApi';

const id = '0x' + '02'.repeat(32);
vi.mock('@/context/AuthContext', () => ({ useAuth: () => ({isAuthenticated:true,isAdmin:true,isIssuer:true,user:{sub:'admin',roles:['admin']}}) }));
vi.mock('@/components/auth/AuthModal', () => ({AuthModal: () => null}));
vi.mock('@/services/issuerApi', () => ({issuerApi:{getIssuer:vi.fn(),getIssuerStatus:vi.fn(),activateLocalIssuer:vi.fn()}}));

beforeEach(() => {cleanup(); vi.clearAllMocks();});

describe('Multi-university workflow', () => {
  it('activates an inspected university and links its exact ID to issuance', async () => {
    vi.mocked(issuerApi.getIssuer).mockResolvedValue({issuer_id:id,display_name:'Second University',status:'ACTIVE',created_at:'2026-11-17',updated_at:'2026-11-17',metadata_uri:null,on_chain_registered:true,on_chain_note:'Database profile'});
    vi.mocked(issuerApi.getIssuerStatus).mockResolvedValue({issuer_id:id,db_status:'ACTIVE',on_chain_status:'ACTIVE',is_on_chain_active:true,checked_at:'2026-11-17'});
    vi.mocked(issuerApi.activateLocalIssuer).mockResolvedValue({status:'CONFIRMED',signing_address:'0x'+'ab'.repeat(20)});
    render(<MemoryRouter><IssuersPage /></MemoryRouter>);
    fireEvent.change(screen.getByPlaceholderText(/issuer ID to inspect/),{target:{value:id}});
    fireEvent.click(screen.getByRole('button',{name:/^Inspect$/}));
    await waitFor(() => expect(screen.getByRole('heading',{name:'Second University'})).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button',{name:'Activate local university'}));
    await waitFor(() => expect(issuerApi.activateLocalIssuer).toHaveBeenCalledWith(id));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('University ready to issue'));
    expect(screen.getByRole('link',{name:'Issue credential for this university'})).toHaveAttribute('href',`/credentials/issue?issuer=${id}`);
  });

  it('prefills an admin-selected university instead of the seeded issuer', () => {
    render(<MemoryRouter initialEntries={[`/credentials/issue?issuer=${id}`]}><CredentialIssuancePage /></MemoryRouter>);
    expect(screen.getByPlaceholderText(/0x2222/)).toHaveValue(id);
  });
});
