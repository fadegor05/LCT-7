import { PageHeader } from '@/components/layout/PageHeader'
import { Breadcrumbs } from '@/components/ui/Breadcrumbs'
import { ButtonLink } from '@/components/ui/Button'
import { Stepper } from '@/components/ui/Stepper'
import { MethodologyEditor } from '@/features/methodology/MethodologyEditor'
import { CREATE_STEPS } from '@/features/new-site/steps'
import styles from '@/features/new-site/NewSite.module.css'
import { useRequiredParam } from '@/lib/useParam'

/** Экран 3 · Методика, шаг 2 создания стройки (UC-2). Стройка уже создана на шаге 1. */
export function NewSiteMethodologyPage() {
  const siteId = useRequiredParam('siteId')

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
        subtitle="Стартовый набор техники предзаполнен по названиям этапов: проверьте его. Правка методики позже пересчитает статусы по загруженным снимкам без повторной обработки изображений."
      />
      <MethodologyEditor siteId={siteId} />
      <div className={styles.footer}>
        <ButtonLink to={`/sites/${siteId}/setup`} variant="ghost">
          Назад
        </ButtonLink>
        <ButtonLink to={`/sites/${siteId}`}>Готово: к стройке</ButtonLink>
      </div>
    </>
  )
}
