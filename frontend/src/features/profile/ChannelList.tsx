import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { QueryState } from '@/components/ui/QueryState'
import {
  useChannels,
  useLinkChannel,
  useToggleChannel,
  useUnlinkChannel,
} from '@/api/notifications'
import styles from './ChannelList.module.css'

const TELEGRAM_TITLE = 'Телеграм'

/** Привязка каналов доставки. Пока канал один — телеграм. */
export function ChannelList() {
  const [awaitingLink, setAwaitingLink] = useState(false)
  const channels = useChannels({ pollWhileEmpty: awaitingLink })
  const link = useLinkChannel()
  const toggle = useToggleChannel()
  const unlink = useUnlinkChannel()

  const handleLink = () => {
    // Вкладку открываем синхронно, прямо в обработчике клика: после ожидания
    // ответа сервера браузер перестаёт считать это действием пользователя, и
    // Safari с Firefox молча блокируют всплывающее окно.
    const popup = window.open('', '_blank')
    if (popup) popup.opener = null
    setAwaitingLink(true)
    link.mutate('telegram', {
      onSuccess: (data) => {
        if (popup) {
          popup.location.href = data.url
        } else {
          window.open(data.url, '_blank', 'noopener')
        }
      },
      onError: () => {
        popup?.close()
        setAwaitingLink(false)
      },
    })
  }

  return (
    <QueryState query={channels}>
      {(data) => {
        const telegram = data.find((channel) => channel.channel === 'telegram')
        return (
          <Card>
            <div className={styles.row}>
              <span className={styles.name}>{TELEGRAM_TITLE}</span>
              {telegram ? (
                <>
                  <span className={styles.address}>{telegram.address_masked}</span>
                  <label className={styles.toggle}>
                    <input
                      type="checkbox"
                      checked={telegram.enabled}
                      onChange={(event) =>
                        toggle.mutate({ channel: 'telegram', enabled: event.target.checked })
                      }
                    />
                    Слать сюда
                  </label>
                  <Button variant="secondary" size="sm" onClick={() => unlink.mutate('telegram')}>
                    Отвязать
                  </Button>
                </>
              ) : (
                <Button size="sm" onClick={handleLink} disabled={link.isPending}>
                  Привязать
                </Button>
              )}
            </div>
            {link.isError && <p className={styles.error}>{link.error.message}</p>}
          </Card>
        )
      }}
    </QueryState>
  )
}
