import React, { useState, useRef, useEffect } from 'react';
import jsQR from 'jsqr';
import {
  Camera,
  Upload,
  X,
  AlertCircle,
  CheckCircle2,
  ScanLine,
  Image as ImageIcon,
} from 'lucide-react';
import { isValidBytes32Hex } from '@/utils/cryptoFormat';

interface QrScannerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onScan: (fingerprint: string) => void;
}

export const QrScannerModal: React.FC<QrScannerModalProps> = ({
  isOpen,
  onClose,
  onScan,
}) => {
  const [mode, setMode] = useState<'upload' | 'camera'>('upload');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [scannedResult, setScannedResult] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Camera refs
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // Extract fingerprint from decoded QR text
  const extractFingerprint = (rawText: string): string | null => {
    const text = rawText.trim();

    // 1. Check if raw text is already a valid 32-byte hex string
    if (isValidBytes32Hex(text)) {
      return text;
    }

    // 2. Try parsing as URL (e.g. /verify?fingerprint=0x...)
    try {
      const url = new URL(text);
      const fp = url.searchParams.get('fingerprint');
      if (fp && isValidBytes32Hex(fp)) {
        return fp;
      }
    } catch {
      // not a full URL, try regex for ?fingerprint=0x[0-9a-fA-F]{64}
      const matchUrl = text.match(/fingerprint=(0x[0-9a-fA-F]{64})/);
      if (matchUrl && isValidBytes32Hex(matchUrl[1])) {
        return matchUrl[1];
      }
    }

    // 3. Try parsing as JSON
    try {
      const obj = JSON.parse(text);
      if (obj.fingerprint && isValidBytes32Hex(obj.fingerprint)) {
        return obj.fingerprint;
      }
    } catch {
      // not json
    }

    // 4. Regex search for any 0x-prefixed 64 hex char sequence
    const hexMatch = text.match(/0x[0-9a-fA-F]{64}/);
    if (hexMatch && isValidBytes32Hex(hexMatch[0])) {
      return hexMatch[0];
    }

    return null;
  };

  const handleDecodedString = (text: string) => {
    const fp = extractFingerprint(text);
    if (fp) {
      setScannedResult(fp);
      setErrorMsg(null);
      stopCamera();
      setTimeout(() => {
        onScan(fp);
        onClose();
      }, 700);
    } else {
      setErrorMsg(
        'Decoded QR does not contain an authoritative 32-byte composite fingerprint.'
      );
    }
  };

  // Decode Image File
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setErrorMsg(null);
    setIsProcessing(true);

    const reader = new FileReader();
    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          setErrorMsg('Failed to initialize 2D image decoding canvas.');
          setIsProcessing(false);
          return;
        }

        ctx.drawImage(img, 0, 0, img.width, img.height);
        const imageData = ctx.getImageData(0, 0, img.width, img.height);
        const code = jsQR(imageData.data, imageData.width, imageData.height);

        setIsProcessing(false);
        if (code && code.data) {
          handleDecodedString(code.data);
        } else {
          setErrorMsg(
            'No valid QR code recognized in this image. Please ensure the QR is clear and well-lit.'
          );
        }
      };
      img.onerror = () => {
        setIsProcessing(false);
        setErrorMsg('Failed to load selected image file.');
      };
      img.src = event.target?.result as string;
    };
    reader.readAsDataURL(file);
  };

  // Live Camera Scan Loop
  const startCamera = async () => {
    setErrorMsg(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.setAttribute('playsinline', 'true');
        await videoRef.current.play();
        scanFrame();
      }
    } catch (err) {
      console.warn('Camera access unavailable:', err);
      setErrorMsg('Camera access was denied or is not supported in this browser. Please use Image Upload mode.');
    }
  };

  const stopCamera = () => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  const scanFrame = () => {
    if (!videoRef.current || !canvasRef.current || videoRef.current.readyState !== videoRef.current.HAVE_ENOUGH_DATA) {
      animFrameRef.current = requestAnimationFrame(scanFrame);
      return;
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    if (ctx) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(imageData.data, imageData.width, imageData.height);

      if (code && code.data) {
        const fp = extractFingerprint(code.data);
        if (fp) {
          handleDecodedString(code.data);
          return;
        }
      }
    }

    animFrameRef.current = requestAnimationFrame(scanFrame);
  };

  useEffect(() => {
    if (isOpen && mode === 'camera') {
      startCamera();
    } else {
      stopCamera();
    }
    return () => stopCamera();
  }, [isOpen, mode]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden space-y-5 p-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-brand-950/80 border border-brand-800/80 rounded-lg text-brand-400">
              <ScanLine className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-100">
                Scan Verification QR Code
              </h3>
              <p className="text-xs text-slate-400">
                Instant Verifier Input Resolution
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              stopCamera();
              onClose();
            }}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Selector Tabs */}
        <div className="grid grid-cols-2 gap-2 p-1 bg-slate-950 border border-slate-800 rounded-xl">
          <button
            type="button"
            onClick={() => {
              stopCamera();
              setMode('upload');
            }}
            className={`flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-colors ${
              mode === 'upload'
                ? 'bg-brand-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Upload className="w-4 h-4" />
            <span>Upload Image</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setMode('camera');
            }}
            className={`flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-colors ${
              mode === 'camera'
                ? 'bg-brand-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Camera className="w-4 h-4" />
            <span>Live Camera</span>
          </button>
        </div>

        {/* Tab 1: Upload Image */}
        {mode === 'upload' && (
          <div className="space-y-4">
            <label className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-slate-700 hover:border-brand-500/80 rounded-xl cursor-pointer bg-slate-950/50 hover:bg-slate-950/80 transition-colors p-6 group">
              <div className="flex flex-col items-center justify-center space-y-2 text-center">
                <div className="p-3 bg-slate-800/80 group-hover:bg-brand-950/80 rounded-full text-slate-400 group-hover:text-brand-400 transition-colors">
                  <ImageIcon className="w-6 h-6" />
                </div>
                <div className="space-y-0.5">
                  <span className="text-xs font-semibold text-slate-200">
                    Click to select or drop QR code image
                  </span>
                  <p className="text-[11px] text-slate-500">
                    Supports PNG, JPG, WEBP, or screenshot snippet
                  </p>
                </div>
              </div>
              <input
                type="file"
                accept="image/*"
                onChange={handleFileUpload}
                className="hidden"
              />
            </label>
            {isProcessing && (
              <p className="text-center text-xs text-brand-400 font-mono animate-pulse">
                Analyzing QR matrix...
              </p>
            )}
          </div>
        )}

        {/* Tab 2: Live Camera View */}
        {mode === 'camera' && (
          <div className="space-y-3">
            <div className="relative w-full h-56 bg-slate-950 rounded-xl overflow-hidden border border-slate-800 flex items-center justify-center">
              <video
                ref={videoRef}
                className="w-full h-full object-cover"
                autoPlay
                muted
              />
              <canvas ref={canvasRef} className="hidden" />

              {/* Reticle Overlay */}
              <div className="absolute inset-0 border-2 border-brand-500/40 pointer-events-none flex items-center justify-center">
                <div className="w-40 h-40 border-2 border-brand-400 rounded-lg animate-pulse" />
              </div>
            </div>
            <p className="text-center text-[11px] text-slate-400">
              Point your camera at a credential verification QR pass.
            </p>
          </div>
        )}

        {/* Success Feedback */}
        {scannedResult && (
          <div className="p-3 bg-emerald-950/60 border border-emerald-800/80 rounded-xl flex items-center gap-2.5 text-xs text-emerald-300">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <div className="truncate">
              <span>Fingerprint Detected:</span>
              <code className="ml-1 font-mono text-[11px] text-emerald-200">
                {scannedResult.slice(0, 14)}...{scannedResult.slice(-6)}
              </code>
            </div>
          </div>
        )}

        {/* Error Feedback */}
        {errorMsg && (
          <div className="p-3 bg-rose-950/60 border border-rose-800/80 rounded-xl flex items-start gap-2 text-xs text-rose-300">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}
      </div>
    </div>
  );
};
