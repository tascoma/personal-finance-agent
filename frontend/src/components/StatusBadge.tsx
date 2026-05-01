interface Props {
  status: string
}

export default function StatusBadge({ status }: Props) {
  return (
    <span className={`badge badge--${status}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}
