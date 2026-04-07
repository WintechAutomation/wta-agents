import { useEffect, useRef } from 'react'
import { io, Socket } from 'socket.io-client'
import { useAgentStore } from '@/store/agentStore'
import type { Message, ToolLog } from '@/types/agent'

let _socket: Socket | null = null

export function useSocket() {
  const { setAgents, setStats, addMessage, setMessages } = useAgentStore()
  const initialized = useRef(false)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true

    _socket = io('/', { path: '/socket.io', transports: ['websocket', 'polling'] })

    _socket.on('connect', () => {
      console.log('[socket] connected')
      // 초기 상태 로드
      fetch('/api/status')
        .then((r) => r.json())
        .then((data) => {
          setAgents(data.agents ?? [])
          setStats(data.stats ?? {})
        })
        .catch(console.error)

      fetch('/api/history?limit=100')
        .then((r) => r.json())
        .then((data) => setMessages(data.messages ?? []))
        .catch(console.error)

      // 도구 사용 로그 초기 로드
      fetch('/api/tool-log/recent?limit=200')
        .then((r) => r.json())
        .then((data) => {
          if (data.ok) useAgentStore.getState().setToolLogs(data.logs ?? [])
        })
        .catch(console.error)

      fetch('/api/tool-log/stats')
        .then((r) => r.json())
        .then((data) => {
          if (data.ok) useAgentStore.getState().setToolStats({ by_agent: data.by_agent, by_tool: data.by_tool })
        })
        .catch(console.error)
    })

    _socket.on('new_message', (msg: Message) => {
      addMessage(msg)
    })

    _socket.on('agent_online', ({ agent_id }: { agent_id: string }) => {
      useAgentStore.getState().updateAgentOnline(agent_id, true)
    })

    _socket.on('agent_offline', ({ agent_id }: { agent_id: string }) => {
      useAgentStore.getState().updateAgentOnline(agent_id, false)
    })

    // 실시간 도구 사용 로그
    _socket.on('tool_log', (log: ToolLog) => {
      useAgentStore.getState().addToolLog(log)
    })

    return () => {
      _socket?.disconnect()
      _socket = null
      initialized.current = false
    }
  }, [])

  return _socket
}
