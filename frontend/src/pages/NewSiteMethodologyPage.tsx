import { useNavigate } from 'react-router'
import { useActivateSite } from '@/api/sites'
import { PageHeader } from '@/components/layout/PageHeader'
import { Breadcrumbs } from '@/components/ui/Breadcrumbs'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Stepper } from '@/components/ui/Stepper'
import { MethodologyEditor } from '@/features/methodology/MethodologyEditor'
import { CREATE_STEPS } from '@/features/new-site/steps'
import styles from '@/features/new-site/NewSite.module.css'
import { useRequiredParam } from '@/lib/useParam'

/** Экран 3 · Методика, шаг 2 создания стройки (UC-2). «Создать стройку» активирует черновик. */
export function NewSiteMethodologyPage() {
  const siteId = useRequiredParam('siteId')
  const navigate = useNavigate()
  const activate = useActivateSite(siteId)

  return (
    <>
      <Breadcrumbs
        items={[
          { label: 'Стройки', to: '/sites' },
          { label: 'Новая стройка', to: `/sites/${siteId}/setup` },
          { label: 'Методика' },
        ]}
      />
      <Stepper steps={CREATE_STEPS} current={1} />
      <PageHeader
        title="Методика: этап → техника"
        subtitle="Стартовый набор техники предзаполнен: проверьте и создайте стройку. После создания правка пересчитает статусы по загруженным кадрам без повторной обработки изображений."
      />
      <MethodologyEditor siteId={siteId} />
      {activate.error && (
        <Callout tone="behind" title="Стройку пока нельзя создать">
          {activate.error.message}
        </Callout>
      )}
      <div className={styles.footer}>
        <ButtonLink to={`/sites/${siteId}/setup`} variant="ghost">
          Назад
        </ButtonLink>
        <Button
          disabled={activate.isPending}
          onClick={() =>
            activate.mutate(undefined, { onSuccess: () => void navigate(`/sites/${siteId}`) })
          }
        >
          Создать стройку
        </Button>
      </div>
    </>
  )
}
