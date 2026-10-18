import { useEffect, useRef, useState } from 'react'
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
  const [snapshotTaken, setSnapshotTaken] = useState(false)
  const refetch = feed.refetch
  const markMutate = markAllRead.mutate

  useEffect(() => {
    let cancelled = false
    // Сначала спрашиваем сервер, и только потом снимаем снимок и помечаем
    // прочитанным. Иначе снимок берётся из кэша возрастом до 30 секунд, а
    // пометка прочитанным на сервере накрывает и то, чего в кэше нет: самое
    // свежее уведомление осталось бы без пометки «новое».
    void (async () => {
      const fresh = await refetch()
      if (cancelled) return
      const unread = (fresh.data?.items ?? [])
        .filter((item) => item.read_at === null)
        .map((item) => item.id)
      snapshot.current = new Set(unread)
      setSnapshotTaken(true)
      if (unread.length > 0) markMutate()
    })()
    return () => {
      cancelled = true
    }
  }, [refetch, markMutate])

  return (
    <Drawer title="Уведомления" onClose={onClose}>
      <QueryState query={feed}>
        {(data) =>
          !snapshotTaken ? (
            <p className={styles.empty} role="status">
              Загрузка…
            </p>
          ) : data.items.length === 0 ? (
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
