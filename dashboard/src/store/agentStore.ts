import { create } from 'zustand'
import type { AgentProfile, AgentStatus, DashboardStats, Message, ToolLog, ToolStats } from '@/types/agent'
import agentsConfig from '@agents'

// 에이전트 프로필 — config/agents.json 단일 소스에서 로드
export const AGENT_PROFILES: Record<string, Omit<AgentProfile, 'online' | 'todayMessages' | 'lastActivity'>> =
  Object.fromEntries(
    Object.entries(agentsConfig)
      .filter(([, a]) => (a as { enabled: boolean }).enabled && (a as { model: unknown }).model && (a as { port: unknown }).port)
      .map(([id, a]) => {
        const ag = a as {
          name: string; emoji: string; role: string
          model: AgentProfile['model']; rank: AgentProfile['rank']
          port: number; room: AgentProfile['room']
        }
        return [id, { id, name: ag.name, emoji: ag.emoji, role: ag.role, model: ag.model, rank: ag.rank, port: ag.port, room: ag.room }]
      })
  )

interface AgentStore {
  agents: AgentStatus[]
  stats: DashboardStats
  messages: Message[]
  toolLogs: ToolLog[]
  toolStats: ToolStats
  setAgents: (agents: AgentStatus[]) => void
  setStats: (stats: DashboardStats) => void
  addMessage: (msg: Message) => void
  setMessages: (msgs: Message[]) => void
  updateAgentOnline: (agentId: string, online: boolean) => void
  addToolLog: (log: ToolLog) => void
  setToolLogs: (logs: ToolLog[]) => void
  setToolStats: (stats: ToolStats) => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  agents: [],
  stats: { online_count: 0, total_agents: 12, total_messages: 0, uptime: '0h 0m' },
  messages: [],
  toolLogs: [],
  toolStats: { by_agent: {}, by_tool: {} },

  setAgents: (agents) => set({ agents }),
  setStats: (stats) => set({ stats }),
  addMessage: (msg) => set((state) => ({
    messages: [...state.messages.slice(-499), msg],
  })),
  setMessages: (msgs) => set({ messages: msgs }),
  updateAgentOnline: (agentId, online) => set((state) => ({
    agents: state.agents.map((a) =>
      a.agent_id === agentId ? { ...a, online } : a
    ),
  })),
  addToolLog: (log) => set((state) => {
    const logs = [...state.toolLogs.slice(-299), log]
    // toolStats 실시간 업데이트
    const byAgent = { ...state.toolStats.by_agent }
    const byTool  = { ...state.toolStats.by_tool }
    byAgent[log.agent_id] = (byAgent[log.agent_id] ?? 0) + 1
    byTool[log.tool_name]  = (byTool[log.tool_name] ?? 0) + 1
    return { toolLogs: logs, toolStats: { by_agent: byAgent, by_tool: byTool } }
  }),
  setToolLogs: (logs) => set({ toolLogs: logs }),
  setToolStats: (stats) => set({ toolStats: stats }),
}))
