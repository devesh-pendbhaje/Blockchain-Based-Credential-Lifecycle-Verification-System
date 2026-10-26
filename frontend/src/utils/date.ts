export function formatDate(dateStrOrTimestamp: string | number | null | undefined): string {
  if (!dateStrOrTimestamp) return '—';

  let date: Date;
  if (typeof dateStrOrTimestamp === 'number') {
    if (dateStrOrTimestamp === 0) return 'Never (Permanent)';
    date = new Date(dateStrOrTimestamp * 1000);
  } else {
    date = new Date(dateStrOrTimestamp);
  }

  if (isNaN(date.getTime())) {
    return String(dateStrOrTimestamp);
  }

  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  }).format(date);
}

export function isTimestampExpired(timestampSeconds: number | null | undefined): boolean {
  if (!timestampSeconds || timestampSeconds === 0) return false;
  const nowSeconds = Math.floor(Date.now() / 1000);
  return timestampSeconds <= nowSeconds;
}
