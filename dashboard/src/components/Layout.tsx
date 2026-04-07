import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { useSocket } from '@/hooks/useSocket'
import { useAgentStore } from '@/store/agentStore'

const NAV_ITEMS = [
  { to: '/office',          label: '에이전트 오피스',  icon: '🏢',  short: '오피스'  },
  { to: '/dashboard',       label: '운영 대시보드',     icon: '⚡',  short: '대시보드' },
  { to: '/overview',        label: '시스템 개요',       icon: '📊',  short: '개요'    },
  { to: '/knowledge',       label: 'Knowledge Base',    icon: '📚',  short: 'KB'      },
  { to: '/task-queue',      label: '작업 큐',           icon: '📋',  short: '작업큐'  },
  { to: '/cron',            label: '스케줄 관리',       icon: '⏰',  short: '스케줄'  },
  { to: '/cs-sessions',     label: 'CS 세션',           icon: '💬',  short: 'CS'      },
  { to: '/glossary',        label: '기술용어집',         icon: '📖',  short: '용어집'  },
  { to: '/manual-builder',  label: '매뉴얼 빌더',       icon: '🔨',  short: '빌더'    },
  { to: '/workspace',       label: '업무공간',           icon: '📁',  short: '공간'    },
  { to: '/captioning',      label: '이미지 캡셔닝',     icon: '📸',  short: '캡셔닝'  },
  { to: '/vector-search',   label: '벡터 검색',          icon: '🔍',  short: '벡터'    },
  { to: '/skills',           label: 'AI 스킬',            icon: '🧠',  short: '스킬'    },
  { to: '/slack-routing',   label: '슬랙 라우팅',         icon: '🔀',  short: '라우팅'  },
  { to: '/graph-rag',       label: '지식그래프',           icon: '🕸️',  short: '그래프'  },
  { to: '/hybrid-search',   label: '하이브리드 검색',      icon: '⚗️',   short: '하이브리드' },
]

function getSavedCollapsed(): boolean {
  try {
    return localStorage.getItem('sidebar-collapsed') === 'true'
  } catch {
    return false
  }
}

export default function Layout() {
  useSocket()
  const stats = useAgentStore((s) => s.stats)
  const [collapsed, setCollapsed] = useState<boolean>(getSavedCollapsed)

  function toggleSidebar() {
    setCollapsed((prev) => {
      const next = !prev
      try { localStorage.setItem('sidebar-collapsed', String(next)) } catch {}
      return next
    })
  }

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-gray-950 text-gray-100 md:overflow-hidden">
      {/* 사이드바 — 데스크톱 전용 */}
      <aside
        className={`hidden md:flex flex-shrink-0 bg-gray-900 border-r border-gray-800 flex-col h-full transition-all duration-200 ${
          collapsed ? 'w-14' : 'w-56'
        }`}
      >
        {/* 헤더 + 토글 버튼 */}
        <div className="p-3 border-b border-gray-800 flex items-center justify-between">
          {!collapsed && (
            <div>
              <div className="text-lg font-bold text-white">WTA AI</div>
              <div className="text-xs text-gray-400 mt-0.5">에이전트 대시보드 v2</div>
            </div>
          )}
          <button
            onClick={toggleSidebar}
            className={`p-1.5 rounded-md text-gray-400 hover:bg-gray-800 hover:text-gray-100 transition-colors ${collapsed ? 'mx-auto' : ''}`}
            title={collapsed ? '사이드바 펼치기' : '사이드바 접기'}
          >
            {collapsed ? '▶' : '◀'}
          </button>
        </div>

        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                `flex items-center rounded-lg text-sm transition-colors ${
                  collapsed ? 'justify-center px-2 py-2.5' : 'gap-2.5 px-3 py-2'
                } ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
                }`
              }
            >
              <span>{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* 시스템 상태 */}
        <div className="p-2 border-t border-gray-800">
          {collapsed ? (
            <div className="flex flex-col items-center gap-1 py-1 text-xs text-gray-400">
              <span title={`온라인 ${stats.online_count}/${stats.total_agents}`} className="text-green-400 font-medium">
                {stats.online_count}
              </span>
            </div>
          ) : (
            <div className="space-y-1">
              <div className="text-xs text-gray-500 px-1">시스템</div>
              <div className="flex items-center justify-between px-3 py-1.5 text-xs text-gray-400">
                <span>온라인</span>
                <span className="text-green-400 font-medium">{stats.online_count}/{stats.total_agents}</span>
              </div>
              <div className="flex items-center justify-between px-3 py-1.5 text-xs text-gray-400">
                <span>업타임</span>
                <span>{stats.uptime}</span>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* 메인 콘텐츠 */}
      <main className="flex-1 overflow-auto min-h-0 pb-16 md:pb-0">
        <Outlet />
      </main>

      {/* 하단 고정 네비게이션 — 모바일 전용 */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-gray-900 border-t border-gray-800">
        <div className="flex overflow-x-auto scrollbar-hide">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center flex-shrink-0 w-[4.5rem] py-2 transition-colors ${
                  isActive ? 'text-blue-400' : 'text-gray-400 active:text-gray-200'
                }`
              }
            >
              <span className="text-xl leading-none">{item.icon}</span>
              <span className="mt-1 text-[10px] leading-none">{item.short}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
