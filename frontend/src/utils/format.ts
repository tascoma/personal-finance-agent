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
  const abs = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n < 0 ? `($${abs})` : `$${abs}`
}

// For debit/credit columns: show the amount only when positive, otherwise em-dash.
export function fmtDebitCredit(val: string | number): string {
  const n = typeof val === 'string' ? parseFloat(val) : val
  return n > 0 ? `$${n.toFixed(2)}` : '—'
}

export function fmtStatus(status: string): string {
  return status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
