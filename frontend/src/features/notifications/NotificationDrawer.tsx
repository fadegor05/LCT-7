import { useEffect, useRef } from 'react'
import { Drawer } from '@/components/ui/Drawer'
import { QueryState } from '@/components/ui/QueryState'
import { useMarkAllRead, useNotifications } from '@/api/notifications'
import { NotificationItem } from './NotificationItem'
import styles from './NotificationDrawer.module.css'

interface NotificationDrawerProps {
  onClose: () => void
}

export function NotificationDrawer({ onClose }: NotificationDrawerProps) {
  const feed = useNotifications()
  const markAllRead = useMarkAllRead()
  // Снимок непрочитанных на момент открытия: пометки «новое» должны дожить
  // до закрытия шторки, хотя на сервере всё уже прочитано
  const snapshot = useRef<Set<string> | null>(null)
  const markMutate = markAllRead.mutate

  useEffect(() => {
    if (snapshot.current !== null || !feed.data) return
    const unread = feed.data.items.filter((item) => item.read_at === null).map((item) => item.id)
    snapshot.current = new Set(unread)
    if (unread.length > 0) markMutate()
  }, [feed.data, markMutate])

  return (
    <Drawer title="Уведомления" onClose={onClose}>
      <QueryState query={feed}>
        {(data) =>
          data.items.length === 0 ? (
            <p className={styles.empty}>Пока ничего не произошло</p>
          ) : (
            <ul className={styles.list}>
              {data.items.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  isNew={snapshot.current?.has(notification.id) ?? false}
                  onNavigate={onClose}
                />
              ))}
            </ul>
          )
        }
      </QueryState>
    </Drawer>
  )
}
