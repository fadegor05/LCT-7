import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { TextField } from '@/components/ui/TextField'
import { useRegister } from '@/api/auth'
import { ApiError } from '@/api/client'
import { AuthBackdrop } from '@/features/auth/AuthBackdrop'
import { getToken } from '@/lib/authStorage'
import styles from './LoginPage.module.css'

const registerSchema = z
  .object({
    login: z
      .string()
      .trim()
      .min(3, 'Логин не короче 3 символов')
      .max(64, 'Логин не должен превышать 64 символа'),
    fullName: z.string().trim().max(255, 'ФИО не должно превышать 255 символов'),
    password: z
      .string()
      .min(8, 'Пароль не короче 8 символов')
      .max(256, 'Пароль не должен превышать 256 символов'),
    passwordConfirm: z.string(),
  })
  .refine((data) => data.password === data.passwordConfirm, {
    path: ['passwordConfirm'],
    message: 'Пароли не совпадают',
  })

type RegisterFormData = z.infer<typeof registerSchema>

/**
 * Страница регистрации. После успеха пользователь сразу входит (бэкенд отдаёт токен).
 * Страница использует стили страницы входа: формы одинаковые.
 */
export function RegisterPage() {
  const navigate = useNavigate()
  const registration = useRegister()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({ resolver: zodResolver(registerSchema) })

  useEffect(() => {
    if (getToken()) {
      void navigate('/', { replace: true })
    }
  }, [navigate])

  const onSubmit = (data: RegisterFormData) => {
    registration.mutate(
      { login: data.login, password: data.password, fullName: data.fullName || undefined },
      { onSuccess: () => void navigate('/sites', { replace: true }) },
    )
  }

  return (
    <div className={styles.container}>
      <AuthBackdrop />
      <Card className={styles.card}>
        <h1 className={styles.title}>Регистрация</h1>
        <form onSubmit={handleSubmit(onSubmit)} className={styles.form}>
          <TextField
            label="Логин"
            type="text"
            error={errors.login?.message}
            disabled={registration.isPending}
            {...register('login')}
          />
          <TextField
            label="ФИО (необязательно)"
            type="text"
            error={errors.fullName?.message}
            disabled={registration.isPending}
            {...register('fullName')}
          />
          <TextField
            label="Пароль"
            type="password"
            error={errors.password?.message}
            disabled={registration.isPending}
            {...register('password')}
          />
          <TextField
            label="Повторите пароль"
            type="password"
            error={errors.passwordConfirm?.message}
            disabled={registration.isPending}
            {...register('passwordConfirm')}
          />
          {registration.isError && (
            <div className={styles.errorMessage}>
              {registration.error instanceof ApiError &&
              typeof registration.error.detail === 'string'
                ? registration.error.detail
                : registration.error.message || 'Ошибка при регистрации'}
            </div>
          )}
          <Button type="submit" disabled={registration.isPending} className={styles.submitButton}>
            {registration.isPending ? 'Загрузка...' : 'Зарегистрироваться'}
          </Button>
        </form>
        <p className={styles.alt}>
          Уже есть аккаунт? <Link to="/login">Войти</Link>
        </p>
      </Card>
    </div>
  )
}
