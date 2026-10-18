import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useNotifications } from '@/api/notifications'
import { NotificationDrawer } from './NotificationDrawer'
import styles from './NotificationBell.module.css'

/** Колокольчик в шапке: бейдж непрочитанных и шторка с лентой. */
export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const feed = useNotifications()
  const unread = feed.data?.unread_count ?? 0

  return (
    <div className={styles.wrap}>
      <Button
        variant="ghost"
        size="icon"
        icon="bell"
        aria-label={unread > 0 ? `Уведомления, непрочитанных: ${unread}` : 'Уведомления'}
        onClick={() => setOpen(true)}
      />
      {unread > 0 && (
        <span className={styles.badge} data-testid="unread-badge">
          {unread}
        </span>
      )}
      {open && <NotificationDrawer onClose={() => setOpen(false)} />}
    </div>
  )
}
