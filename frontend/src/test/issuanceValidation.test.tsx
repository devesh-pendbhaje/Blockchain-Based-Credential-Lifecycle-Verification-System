import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CredentialIssuancePage } from '@/pages/CredentialIssuancePage';

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true, isAdmin: true, isIssuer: true,
    user: { sub: 'admin', roles: ['admin'] } }),
}));
vi.mock('@/components/auth/AuthModal', () => ({ AuthModal: () => null }));

describe('Issuance wizard validation', () => {
  it('reveals a missing issuer on review and allows confirmation after correction without losing digests', async () => {
    render(<MemoryRouter><CredentialIssuancePage /></MemoryRouter>);
    const hash = '0x' + '12'.repeat(32);
    fireEvent.click(screen.getByRole('button', { name: /Step 2 Document/ }));
    fireEvent.change(screen.getByPlaceholderText(/Auto-populated upon certificate upload/), { target: { value: hash } });
    fireEvent.click(screen.getByRole('button', { name: /Step 3 Metadata/ }));
    fireEvent.change(screen.getByPlaceholderText(/Auto-populated by canonicalizer/), { target: { value: hash } });
    fireEvent.click(screen.getByRole('button', { name: /Step 4 Salted/ }));
    fireEvent.change(screen.getByPlaceholderText(/Auto-populated by tree builder/), { target: { value: hash } });
    fireEvent.click(screen.getByRole('button', { name: /Step 5 Review/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Issue Credential Record' }));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/Step 1: Issuer ID/));
    expect(screen.getByRole('heading', { name: 'Step 1: Credential & Issuer Identifiers' })).toBeInTheDocument();
    expect(screen.queryByText('Confirm Credential Issuance')).not.toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/0x2222/), { target: { value: hash } });
    fireEvent.click(screen.getByRole('button', { name: /Step 5 Review/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Issue Credential Record' }));
    await waitFor(() => expect(screen.getByText('Confirm Credential Issuance')).toBeInTheDocument());
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
