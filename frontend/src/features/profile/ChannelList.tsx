import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { QueryState } from '@/components/ui/QueryState'
import {
  useChannels,
  useLinkChannel,
  useToggleChannel,
  useUnlinkChannel,
} from '@/api/notifications'
import type { UserChannel } from '@/api/schemas'
import styles from './ChannelList.module.css'

const EMAIL_RESULT: Record<string, { text: string; error: boolean }> = {
  confirmed: { text: 'Почта подтверждена', error: false },
  invalid: { text: 'Ссылка из письма недействительна или устарела', error: true },
}

/** Привязка каналов доставки: телеграм и почта. */
export function ChannelList() {
  const [awaitingLink, setAwaitingLink] = useState(false)
  const [emailSent, setEmailSent] = useState(false)
  const [address, setAddress] = useState('')
  const [params] = useSearchParams()
  const channels = useChannels({ pollUntil: awaitingLink ? 'telegram' : undefined })
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
    link.mutate(
      { channel: 'telegram' },
      {
        onSuccess: (data) => {
          if (!data.url) return
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
      },
    )
  }

  const handleEmailLink = () => {
    setEmailSent(false)
    link.mutate(
      { channel: 'email', address: address.trim() },
      { onSuccess: () => setEmailSent(true) },
    )
  }

  const emailResult = EMAIL_RESULT[params.get('email') ?? '']

  const renderBound = (binding: UserChannel) => (
    <>
      <span className={styles.address}>{binding.address_masked}</span>
      <label className={styles.toggle}>
        <input
          type="checkbox"
          checked={binding.enabled}
          onChange={(event) =>
            toggle.mutate({ channel: binding.channel, enabled: event.target.checked })
          }
        />
        Слать сюда
      </label>
      <Button variant="secondary" size="sm" onClick={() => unlink.mutate(binding.channel)}>
        Отвязать
      </Button>
    </>
  )

  return (
    <QueryState query={channels}>
      {(data) => {
        const telegram = data.find((channel) => channel.channel === 'telegram')
        const email = data.find((channel) => channel.channel === 'email')
        return (
          <Card>
            <div className={styles.row}>
              <span className={styles.name}>Телеграм</span>
              {telegram ? (
                renderBound(telegram)
              ) : (
                <Button size="sm" onClick={handleLink} disabled={link.isPending}>
                  Привязать
                </Button>
              )}
            </div>
            <div className={styles.row}>
              <span className={styles.name}>Почта</span>
              {email ? (
                renderBound(email)
              ) : (
                <>
                  <input
                    className={styles.input}
                    type="email"
                    aria-label="Адрес почты"
                    placeholder="name@example.com"
                    value={address}
                    onChange={(event) => setAddress(event.target.value)}
                  />
                  <Button
                    size="sm"
                    onClick={handleEmailLink}
                    disabled={link.isPending || !address.trim()}
                  >
                    Привязать почту
                  </Button>
                </>
              )}
            </div>
            {!email && emailSent && (
              <p className={styles.hint}>Письмо отправлено. Перейдите по ссылке из него.</p>
            )}
            {!email && emailResult && (
              <p className={emailResult.error ? styles.error : styles.hint}>{emailResult.text}</p>
            )}
            {link.isError && <p className={styles.error}>{link.error.message}</p>}
          </Card>
        )
      }}
    </QueryState>
  )
}
