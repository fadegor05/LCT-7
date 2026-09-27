import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useNavigate, useParams } from 'react-router'
import { useScheduleImport, useStages, useUpdateStage, useUploadSchedule } from '@/api/schedule'
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
import { formatFileSize } from '@/lib/format'

const ACCEPT =
  '.csv,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

const defaults: SiteCreate = { name: '', address: '', object_type: 'housing', work_days: 'mon_fri' }

function toForm(site: Site | undefined): SiteCreate | undefined {
  return (
    site && {
      name: site.name,
      address: site.address ?? '',
      object_type: site.object_type,
      work_days: site.work_days,
    }
  )
}

/**
 * Экран 2 · Новая стройка, шаг 1 (UC-1). Черновик стройки создаётся при первой загрузке
 * графика — тогда URL меняется на /sites/:id/setup, и шаг можно открыть заново.
 */
export function NewSitePage() {
  const { siteId } = useParams()
  const navigate = useNavigate()
  const site = useSite(siteId ?? '')
  const scheduleImport = useScheduleImport(siteId)
  const stages = useStages(siteId)
  const createSite = useCreateSite()
  const updateSite = useUpdateSite(siteId ?? '')
  const upload = useUploadSchedule()
  const updateStage = useUpdateStage(siteId ?? '')

  const form = useForm<SiteCreate>({
    resolver: zodResolver(siteCreateSchema),
    defaultValues: defaults,
    values: siteId ? toForm(site.data) : undefined,
  })

  const onFiles = (files: File[]) =>
    form.handleSubmit(async (values) => {
      try {
        const target = siteId ?? (await createSite.mutateAsync(values)).id
        await upload.mutateAsync({ siteId: target, file: files[0]! })
        if (!siteId) void navigate(`/sites/${target}/setup`, { replace: true })
      } catch {
        // Ошибка уже в состоянии мутации и показана в Callout ниже.
      }
    })()

  const onNext = form.handleSubmit(async (values) => {
    await updateSite.mutateAsync(values)
    void navigate(`/sites/${siteId}/setup/methodology`)
  })

  const current = scheduleImport.data
  const canProceed = Boolean(siteId && current && current.window_overlaps === 0)
  const error = createSite.error ?? upload.error ?? updateSite.error ?? updateStage.error

  return (
    <>
      <Breadcrumbs items={[{ label: 'Стройки', to: '/sites' }, { label: 'Новая стройка' }]} />
      <h1>Новая стройка</h1>
      <Stepper steps={CREATE_STEPS} current={0} />

      <ObjectForm register={form.register} control={form.control} errors={form.formState.errors} />

      <Card>
        <h3>График работ</h3>
        {current ? (
          <>
            <div className={styles.fileRow}>
              <span className="data">
                {current.file_name} · {formatFileSize(current.file_size)}
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
            hint="CSV или Excel: этапы работ и плановые даты. Техника в файле не нужна."
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

      {current && stages.data && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <SectionHeader
            level={3}
            title="Крупные этапы"
            description="Мелкие работы из файла сгруппированы в крупные последовательные этапы. Проверьте состав, даты и сопоставление со справочником."
          />
          <StagesTable
            stages={stages.data}
            year={Number(current.uploaded_at.slice(0, 4))}
            pending={updateStage.isPending}
            onConfirmMatch={(stageId) =>
              updateStage.mutate({ stageId, data: { match_confirmed: true } })
            }
            onSetDates={(stageId, start, end) =>
              updateStage.mutate({ stageId, data: { planned_start: start, planned_end: end } })
            }
          />
          <p className="sm muted">
            Этапы идут строго друг за другом. Работу можно перенести в другой этап или объединить
            два соседних. Технику задаёт методика на крупный этап.
          </p>
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
