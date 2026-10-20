import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { request } from './client'
import { keys } from './keys'
import {
  channelLinkSchema,
  markReadSchema,
  notificationListSchema,
  notificationSchema,
  userChannelSchema,
  type ChannelKind,
} from './schemas'

/** Пока пользователь ушёл в телеграм нажимать «Запустить» */
const CHANNEL_POLL_MS = 2000

interface TestNotification {
  title?: string
  body?: string
  link?: string | null
}

export const notificationsApi = {
  list: () => request('/notifications', { schema: notificationListSchema }),
  markAllRead: () => request('/notifications/read', { method: 'POST', schema: markReadSchema }),
  createTest: (body: TestNotification) =>
    request('/notifications/test', { method: 'POST', body, schema: notificationSchema }),
  sendDigest: () =>
    request('/notifications/digest', { method: 'POST', schema: notificationSchema }),
  listChannels: () => request('/users/me/channels', { schema: z.array(userChannelSchema) }),
  link: (channel: ChannelKind, address?: string) =>
    request(`/users/me/channels/${channel}/link`, {
      method: 'POST',
      body: address ? { address } : undefined,
      schema: channelLinkSchema,
    }),
  toggle: (channel: ChannelKind, enabled: boolean) =>
    request(`/users/me/channels/${channel}`, {
      method: 'PATCH',
      body: { enabled },
      schema: userChannelSchema,
    }),
  unlink: (channel: ChannelKind) => request(`/users/me/channels/${channel}`, { method: 'DELETE' }),
}

/** Лента и счётчик непрочитанных. Опрос раз в полминуты — вебсокетов в проекте нет. */
export function useNotifications() {
  return useQuery({
    queryKey: keys.notifications,
    queryFn: notificationsApi.list,
    refetchInterval: 30_000,
  })
}

export function useMarkAllRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.notifications }),
  })
}

export function useCreateTestNotification() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TestNotification) => notificationsApi.createTest(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.notifications }),
  })
}

/** «Отправить сводку сейчас»: сводка по объектам уходит в ленту и привязанные каналы. */
export function useSendDigest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: notificationsApi.sendDigest,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.notifications }),
  })
}

/**
 * Привязки каналов. `refetchInterval` нужен, пока пользователь ушёл в телеграм
 * нажимать «Запустить»: привязку создаёт фоновый поллер бота, и без опроса
 * страница узнает о ней только после перезагрузки.
 */
export function useChannels({ pollUntil }: { pollUntil?: ChannelKind } = {}) {
  return useQuery({
    queryKey: keys.channels,
    queryFn: notificationsApi.listChannels,
    // Опрашиваем, только пока ждём привязку, и прекращаем, как только она пришла
    refetchInterval: (query) =>
      pollUntil && !query.state.data?.some((channel) => channel.channel === pollUntil)
        ? CHANNEL_POLL_MS
        : false,
  })
}

export function useLinkChannel() {
  return useMutation({
    mutationFn: ({ channel, address }: { channel: ChannelKind; address?: string }) =>
      notificationsApi.link(channel, address),
  })
}

export function useToggleChannel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ channel, enabled }: { channel: ChannelKind; enabled: boolean }) =>
      notificationsApi.toggle(channel, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.channels }),
  })
}

export function useUnlinkChannel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (channel: ChannelKind) => notificationsApi.unlink(channel),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.channels }),
  })
}
