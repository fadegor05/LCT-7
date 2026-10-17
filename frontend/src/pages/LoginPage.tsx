import { useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { TextField } from '@/components/ui/TextField'
import { useLogin } from '@/api/auth'
import { ApiError } from '@/api/client'
import { AuthBackdrop } from '@/features/auth/AuthBackdrop'
import { getToken } from '@/lib/authStorage'
import styles from './LoginPage.module.css'

const loginSchema = z.object({
  login: z.string().min(1, 'Укажите логин').max(64, 'Логин не должен превышать 64 символа'),
  password: z.string().min(1, 'Укажите пароль').max(256, 'Пароль не должен превышать 256 символов'),
})

type LoginFormData = z.infer<typeof loginSchema>

/**
 * Страница входа. Если пользователь уже авторизован (есть токен), перенаправляет на главную.
 */
export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const login = useLogin()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  // Redirect if already authenticated
  useEffect(() => {
    if (getToken()) {
      void navigate('/', { replace: true })
    }
  }, [navigate])

  const onSubmit = (data: LoginFormData) => {
    login.mutate(data, {
      onSuccess: () => {
        const from = (location.state as { from?: string } | undefined)?.from || '/sites'
        void navigate(from, { replace: true })
      },
    })
  }

  return (
    <div className={styles.container}>
      <AuthBackdrop />
      <Card className={styles.card}>
        <h1 className={styles.title}>Вход</h1>
        <form onSubmit={handleSubmit(onSubmit)} className={styles.form}>
          <TextField
            label="Логин"
            type="text"
            placeholder="Например, ivanov"
            autoComplete="username"
            error={errors.login?.message}
            disabled={login.isPending}
            {...register('login')}
          />
          <TextField
            label="Пароль"
            type="password"
            placeholder="Введите пароль"
            autoComplete="current-password"
            error={errors.password?.message}
            disabled={login.isPending}
            {...register('password')}
          />
          {login.isError && (
            <div className={styles.errorMessage}>
              {login.error instanceof ApiError && typeof login.error.detail === 'string'
                ? login.error.detail
                : login.error.message || 'Ошибка при входе'}
            </div>
          )}
          <Button type="submit" disabled={login.isPending} className={styles.submitButton}>
            {login.isPending ? 'Загрузка...' : 'Вход'}
          </Button>
        </form>
        <p className={styles.alt}>
          Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
        </p>
      </Card>
    </div>
  )
}
