// 에이전트 도메인 타입

export type AgentRank = '부장' | '대리' | '사원'
export type AgentModel = 'claude-opus-4' | 'claude-sonnet-4-6' | 'claude-haiku-4-5' | string

export interface AgentProfile {
  id: string
  name: string
  emoji: string
  role: string
  model: AgentModel
  rank: AgentRank
  port: number
  room: AgentRoom
  online: boolean
  todayMessages: number
  lastActivity: string | null
}

export type AgentRoom = 'max' | 'quality' | 'dev' | 'cs' | 'management'

export interface AgentStatus {
  agent_id: string
  name: string
  emoji: string
  role: string
  online: boolean
  last_heartbeat: string | null
}

export interface DashboardStats {
  online_count: number
  total_agents: number
  total_messages: number
  uptime: string
}

export interface StatusSnapshot {
  agents: AgentStatus[]
  stats: DashboardStats
}

export interface Message {
  id: number
  from: string
  to: string
  content: string
  type: 'chat' | 'telegram' | 'system'
  time: string
}

export interface ToolLog {
  agent_id: string
  tool_name: string
  timestamp: string
}

export interface ToolStats {
  by_agent: Record<string, number>
  by_tool: Record<string, number>
}
