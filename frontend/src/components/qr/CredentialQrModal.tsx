import React, { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import {
  QrCode,
  Download,
  Copy,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  X,
} from 'lucide-react';
import { HashBadge } from '@/components/status/HashBadge';

interface CredentialQrModalProps {
  isOpen: boolean;
  onClose: () => void;
  fingerprint: string;
  credentialId?: string;
  version?: number;
}

export const CredentialQrModal: React.FC<CredentialQrModalProps> = ({
  isOpen,
  onClose,
  fingerprint,
  credentialId,
  version,
}) => {
  const [qrDataUrl, setQrDataUrl] = useState<string>('');
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedFp, setCopiedFp] = useState(false);

  const verificationUrl = typeof window !== 'undefined'
    ? `${window.location.origin}/verify?fingerprint=${encodeURIComponent(fingerprint)}`
    : `https://verification.local/verify?fingerprint=${fingerprint}`;

  useEffect(() => {
    if (!isOpen || !fingerprint) return;

    QRCode.toDataURL(verificationUrl, {
      width: 320,
      margin: 2,
      color: {
        dark: '#020617', // slate-950
        light: '#ffffff',
      },
      errorCorrectionLevel: 'M',
    })
      .then((url) => setQrDataUrl(url))
      .catch((err) => console.error('Failed to generate QR code', err));
  }, [isOpen, fingerprint, verificationUrl]);

  if (!isOpen) return null;

  const handleCopyLink = async () => {
    await navigator.clipboard.writeText(verificationUrl);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleCopyFp = async () => {
    await navigator.clipboard.writeText(fingerprint);
    setCopiedFp(true);
    setTimeout(() => setCopiedFp(false), 2000);
  };

  const handleDownload = () => {
    if (!qrDataUrl) return;
    const a = document.createElement('a');
    a.href = qrDataUrl;
    a.download = `credential-qr-${fingerprint.slice(0, 10)}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden space-y-6 p-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-brand-950/80 border border-brand-800/80 rounded-lg text-brand-400">
              <QrCode className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-100">
                Verification QR Pass
              </h3>
              <p className="text-xs text-slate-400">
                Instant Verifier Scan & Public Portal Anchor
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* QR Code Presentation */}
        <div className="flex flex-col items-center justify-center space-y-3">
          <div className="p-3 bg-white rounded-2xl shadow-inner border-4 border-slate-800/80 flex items-center justify-center">
            {qrDataUrl ? (
              <img
                src={qrDataUrl}
                alt="Credential Verification QR Code"
                className="w-56 h-56 rounded-xl"
              />
            ) : (
              <div className="w-56 h-56 flex items-center justify-center text-xs text-slate-500 font-mono">
                Generating QR...
              </div>
            )}
          </div>

          {/* Zero-PII Guarantee Badge */}
          <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-950/50 border border-emerald-800/60 rounded-full text-[11px] text-emerald-300 font-medium">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Strict Zero-PII: Encodes only public composite fingerprint</span>
          </div>
        </div>

        {/* Metadata Details */}
        <div className="p-3.5 bg-slate-950/60 border border-slate-800 rounded-xl space-y-2 text-xs">
          <div className="flex justify-between items-center text-slate-400">
            <span>Composite Fingerprint</span>
            <button
              onClick={handleCopyFp}
              className="text-[11px] text-brand-400 hover:text-brand-300 flex items-center gap-1 font-mono"
            >
              {copiedFp ? <CheckCircle2 className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              <span>{copiedFp ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
          <div className="truncate">
            <HashBadge hash={fingerprint} truncate={false} />
          </div>

          {(credentialId || version) && (
            <div className="flex items-center justify-between pt-1 border-t border-slate-800/60 text-[11px] text-slate-500">
              {credentialId && <span>ID: <code className="text-slate-400">{credentialId.slice(0, 14)}...</code></span>}
              {version && <span>Version: <strong className="text-slate-300">v{version}</strong></span>}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="grid grid-cols-2 gap-2.5 pt-1">
          <button
            onClick={handleCopyLink}
            className="flex items-center justify-center gap-2 px-3.5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-medium transition-colors border border-slate-700"
          >
            {copiedLink ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            <span>{copiedLink ? 'Link Copied!' : 'Copy Link'}</span>
          </button>

          <button
            onClick={handleDownload}
            disabled={!qrDataUrl}
            className="flex items-center justify-center gap-2 px-3.5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-xl text-xs font-semibold tracking-wide transition-colors shadow-lg shadow-brand-950 disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
            <span>Download PNG</span>
          </button>
        </div>

        {/* Direct Link */}
        <div className="text-center pt-1">
          <a
            href={verificationUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-brand-400 transition-colors"
          >
            <span>Open Public Verification Page directly</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </div>
  );
};
