import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { request } from './client'
import { keys } from './keys'
import { loginResponseSchema, userSchema } from './schemas'
import { setToken } from '@/lib/authStorage'

export const authApi = {
  login: (login: string, password: string) =>
    request('/auth/login', {
      method: 'POST',
      body: { login, password },
      schema: loginResponseSchema,
    }),
  me: () => request('/users/me', { schema: userSchema }),
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ login, password }: { login: string; password: string }) =>
      authApi.login(login, password),
    onSuccess: (data) => {
      setToken(data.access_token)
      qc.setQueryData(keys.me, data.user)
    },
  })
}

export function useMe() {
  return useQuery({ queryKey: keys.me, queryFn: authApi.me })
}
