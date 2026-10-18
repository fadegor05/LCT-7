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
  const channels = useChannels()
  const link = useLinkChannel()
  const toggle = useToggleChannel()
  const unlink = useUnlinkChannel()

  const handleLink = () => {
    link.mutate('telegram', {
      onSuccess: (data) => {
        // Пользователь уходит в телеграм и жмёт «Запустить»; привязку поймает
        // следующий опрос списка каналов
        window.open(data.url, '_blank', 'noopener')
        void channels.refetch()
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
