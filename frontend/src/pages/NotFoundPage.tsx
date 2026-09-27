import { PageHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'

export function NotFoundPage() {
  return (
    <PageHeader
      title="Страница не найдена"
      subtitle="Такого адреса нет. Вернитесь к списку строек."
      actions={
        <ButtonLink to="/sites" variant="ghost">
          К стройкам
        </ButtonLink>
      }
    />
  )
}
