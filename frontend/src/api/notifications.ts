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
  listChannels: () => request('/users/me/channels', { schema: z.array(userChannelSchema) }),
  link: (channel: ChannelKind) =>
    request(`/users/me/channels/${channel}/link`, {
      method: 'POST',
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

export function useChannels() {
  return useQuery({ queryKey: keys.channels, queryFn: notificationsApi.listChannels })
}

export function useLinkChannel() {
  return useMutation({ mutationFn: (channel: ChannelKind) => notificationsApi.link(channel) })
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
