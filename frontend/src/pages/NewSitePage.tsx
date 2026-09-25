import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useNavigate, useParams } from 'react-router'
import { useSchedule, useUpdateStageDates, useUploadSchedule } from '@/api/schedule'
import { siteCreateSchema, type Site, type SiteCreate } from '@/api/schemas'
import { useCreateSite, useSite, useUpdateSite } from '@/api/sites'
import { SectionHeader } from '@/components/layout/PageHeader'
import { Breadcrumbs } from '@/components/ui/Breadcrumbs'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Card } from '@/components/ui/Card'
import { FileDrop } from '@/components/ui/FileDrop'
import { Stepper } from '@/components/ui/Stepper'
import { ImportSummary } from '@/features/new-site/ImportSummary'
import { ObjectForm } from '@/features/new-site/ObjectForm'
import { StagesTable } from '@/features/new-site/StagesTable'
import { CREATE_STEPS } from '@/features/new-site/steps'
import styles from '@/features/new-site/NewSite.module.css'
import { formatDateTime } from '@/lib/format'

const ACCEPT =
  '.csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

const defaults: SiteCreate = { name: '', address: '' }

function toForm(site: Site | undefined): SiteCreate | undefined {
  return site && { name: site.name, address: site.address ?? '' }
}

/**
 * Экран 2 · Новая стройка, шаг 1 (UC-1). Стройка создаётся при первой загрузке графика —
 * тогда URL меняется на /sites/:id/setup, и шаг можно открыть заново.
 */
export function NewSitePage() {
  const { siteId } = useParams()
  const navigate = useNavigate()
  const site = useSite(siteId ?? '')
  const schedule = useSchedule(siteId)
  const createSite = useCreateSite()
  const updateSite = useUpdateSite(siteId ?? '')
  const upload = useUploadSchedule()
  const updateStage = useUpdateStageDates(siteId ?? '')

  const form = useForm<SiteCreate>({
    resolver: zodResolver(siteCreateSchema),
    defaultValues: defaults,
    values: siteId ? toForm(site.data) : undefined,
  })

  const onFiles = (files: File[]) =>
    form.handleSubmit(async (values) => {
      try {
        const target = siteId ?? (await createSite.mutateAsync(values)).id
        if (!siteId) void navigate(`/sites/${target}/setup`, { replace: true })
        await upload.mutateAsync({ siteId: target, file: files[0]! })
      } catch {
        // Ошибка уже в состоянии мутации и показана в Callout ниже.
      }
    })()

  const onNext = form.handleSubmit(async (values) => {
    await updateSite.mutateAsync(values)
    void navigate(`/sites/${siteId}/setup/methodology`)
  })

  const current = schedule.data
  const canProceed = Boolean(siteId && current)
  const error = createSite.error ?? upload.error ?? updateSite.error ?? updateStage.error

  return (
    <>
      <Breadcrumbs items={[{ label: 'Стройки', to: '/sites' }, { label: 'Новая стройка' }]} />
      <h1>Новая стройка</h1>
      <Stepper steps={CREATE_STEPS} current={0} />

      <ObjectForm register={form.register} errors={form.formState.errors} />

      <Card>
        <h3>График работ</h3>
        {current ? (
          <>
            <div className={styles.fileRow}>
              <span className="data">
                {current.source_filename} · загружен {formatDateTime(current.imported_at)}
              </span>
              <label className="sm">
                <input
                  type="file"
                  accept={ACCEPT}
                  className="srOnly"
                  onChange={(event) => {
                    const file = event.target.files?.[0]
                    if (file) void onFiles([file])
                  }}
                />
                <span
                  style={{ textDecoration: 'underline', color: 'var(--link)', cursor: 'pointer' }}
                >
                  Заменить файл
                </span>
              </label>
            </div>
            <ImportSummary data={current} />
          </>
        ) : (
          <FileDrop
            title="Перетащите файл графика"
            hint="CSV или XLSX до 5 МБ: этапы работ и плановые даты. Техника в файле не нужна."
            accept={ACCEPT}
            disabled={upload.isPending || createSite.isPending}
            onFiles={(files) => void onFiles(files)}
          />
        )}
        {(upload.isPending || createSite.isPending) && (
          <p className="muted" role="status">
            Разбираем график…
          </p>
        )}
      </Card>

      {current && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <SectionHeader
            level={3}
            title="Этапы"
            description="Этапы и плановые даты из файла. Технику задаёт методика на следующем шаге. Повторная загрузка файла заменит график целиком, включая даты, заданные вручную."
          />
          <StagesTable
            stages={current.stages}
            year={Number(current.imported_at.slice(0, 4))}
            pending={updateStage.isPending}
            onSetDates={(stageId, start, end) =>
              updateStage.mutate({ stageId, data: { planned_start: start, planned_end: end } })
            }
          />
        </section>
      )}

      {error && (
        <Callout tone="behind" title="Не получилось">
          {error.message}
        </Callout>
      )}

      <div className={styles.footer}>
        <ButtonLink to="/sites" variant="ghost">
          Отмена
        </ButtonLink>
        <Button onClick={() => void onNext()} disabled={!canProceed || updateSite.isPending}>
          Далее: методика
        </Button>
      </div>
    </>
  )
}
