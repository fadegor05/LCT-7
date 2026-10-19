import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { TextField } from '@/components/ui/TextField'
import { request } from '@/api/client'
import { keys } from '@/api/keys'
import { userSchema } from '@/api/schemas'
import { useMe } from '@/api/auth'
import { ChannelList } from '@/features/profile/ChannelList'
import styles from './ProfilePage.module.css'

export function ProfilePage() {
  const me = useMe()
  const qc = useQueryClient()
  // Черновик поверх серверного значения: пока пользователь не правил поле,
  // показываем то, что пришло из /users/me. Эффект с setState тут не нужен.
  const [draft, setDraft] = useState<string | null>(null)
  const fullName = draft ?? me.data?.full_name ?? ''

  const rename = useMutation({
    mutationFn: (value: string) =>
      request('/users/me', { method: 'PATCH', body: { full_name: value }, schema: userSchema }),
    onSuccess: (user) => qc.setQueryData(keys.me, user),
  })

  return (
    <div className={styles.page}>
      <PageHeader title="Личный кабинет" />
      <Card>
        <form
          className={styles.form}
          onSubmit={(event) => {
            event.preventDefault()
            rename.mutate(fullName)
          }}
        >
          <TextField
            label="ФИО"
            value={fullName}
            onChange={(event) => setDraft(event.target.value)}
          />
          <Button type="submit" disabled={rename.isPending || fullName.trim().length === 0}>
            Сохранить
          </Button>
        </form>
      </Card>
      <h2 className={styles.subtitle}>Куда слать уведомления</h2>
      <ChannelList />
    </div>
  )
}
