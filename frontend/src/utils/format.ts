const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']

export function fmtPeriod(isoDate: string): string {
  const [, m] = isoDate.split('-')
  const year = isoDate.slice(0, 4)
  return `${MONTHS[parseInt(m, 10) - 1]} ${year}`
}

export function fmtDate(isoDate: string): string {
  return isoDate.slice(0, 10)
}

export function fmtMoney(val: string | number): string {
  const n = typeof val === 'string' ? parseFloat(val) : val
  if (n < 0) return `$(${Math.abs(n).toFixed(2)})`
  return `$${n.toFixed(2)}`
}

export function fmtStatus(status: string): string {
  return status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
