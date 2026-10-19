import { Link } from 'react-router'
import type { Notification } from '@/api/schemas'
import styles from './NotificationItem.module.css'

interface NotificationItemProps {
  notification: Notification
  isNew: boolean
  onNavigate: () => void
}

/** Дата в формате ленты: «18.10, 14:30». */
function formatMoment(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function NotificationItem({ notification, isNew, onNavigate }: NotificationItemProps) {
  const content = (
    <>
      <div className={styles.head}>
        <span className={styles.title}>{notification.title}</span>
        {isNew && <span className={styles.badge}>новое</span>}
      </div>
      <p className={styles.body}>{notification.body}</p>
      <time className={styles.time} dateTime={notification.created_at}>
        {formatMoment(notification.created_at)}
      </time>
    </>
  )

  if (notification.link) {
    return (
      <li className={styles.item}>
        <Link to={notification.link} className={styles.link} onClick={onNavigate}>
          {content}
        </Link>
      </li>
    )
  }
  return <li className={styles.item}>{content}</li>
}
