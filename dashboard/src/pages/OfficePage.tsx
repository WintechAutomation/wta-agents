// 에이전트 오피스 — 한국 직장인 픽셀아트 캐릭터 (Phase 4 — 밝은 오피스)
import { useState, useEffect, useRef } from 'react'
import { Application, Graphics, Container, Ticker, Text, TextStyle } from 'pixi.js'
import { useAgentStore, AGENT_PROFILES } from '@/store/agentStore'
import agentsConfig from '@agents'

// ── 팔레트 ────────────────────────────────────────────────────
const P = {
  SK:   0xFFCCB4,
  EY:   0x1F2937,
  MO:   0xD46060,
  DT:   0xC4A35A,
  DF:   0x9B7E32,
  SUIT: 0x1E293B,
  WH:   0xF1F5F9,
  GLS:  0x475569,
  TIE:  0xDC2626,
}

// ── 스프라이트 (10 cols × 15 rows, scale 4) ─────────────────
const SPRITE_OPUS: number[][] = [
  [0, 0, 2, 2, 2, 2, 2, 2, 0, 0],
  [0, 0, 2, 0, 0, 0, 0, 2, 0, 0],
  [0, 0, 1, 1, 1, 1, 1, 1, 0, 0],
  [0, 1, 1, 1, 1, 1, 1, 1, 1, 0],
  [0, 1,11, 5, 1, 1, 5,11, 1, 0],
  [0, 1,11, 1, 1, 1, 1,11, 1, 0],
  [0, 1, 1, 1, 6, 6, 1, 1, 1, 0],
  [0, 0, 1, 1, 1, 1, 1, 1, 0, 0],
  [0, 0, 9, 9,10, 9, 9, 0, 0, 0],
  [4, 4, 9, 9,10, 9, 9, 4, 4, 0],
  [4, 4, 4, 9,10, 9, 4, 4, 4, 0],
  [1, 4, 4, 9,10, 9, 4, 4, 1, 0],
  [1, 1, 7, 7, 7, 7, 7, 7, 1, 1],
  [0, 0, 7, 7, 7, 7, 7, 7, 0, 0],
  [0, 0, 8, 8, 8, 8, 8, 8, 0, 0],
]

const SPRITE_SONNET: number[][] = [
  [0, 0, 2, 2, 2, 2, 2, 2, 0, 0],
  [0, 2, 2, 2, 2, 2, 2, 2, 2, 0],
  [0, 0, 1, 1, 1, 1, 1, 1, 0, 0],
  [0, 1, 1, 1, 1, 1, 1, 1, 1, 0],
  [0, 1, 5, 1, 1, 1, 1, 5, 1, 0],
  [0, 1, 1, 1, 1, 1, 1, 1, 1, 0],
  [0, 1, 1, 1, 6, 6, 1, 1, 1, 0],
  [0, 0, 1, 1, 1, 1, 1, 1, 0, 0],
  [0, 0, 9, 9, 9, 9, 9, 0, 0, 0],
  [0, 3, 3, 9, 9, 9, 3, 3, 0, 0],
  [0, 3, 3, 3, 3, 3, 3, 3, 0, 0],
  [1, 3, 3, 3, 3, 3, 3, 3, 1, 0],
  [1, 1, 7, 7, 7, 7, 7, 7, 1, 1],
  [0, 0, 7, 7, 7, 7, 7, 7, 0, 0],
  [0, 0, 8, 8, 8, 8, 8, 8, 0, 0],
]

const SPRITE_HAIKU: number[][] = [
  [0, 2, 0, 2, 0, 2, 0, 2, 0, 0],
  [0, 2, 2, 2, 2, 2, 2, 2, 2, 0],
  [0, 0, 1, 1, 1, 1, 1, 1, 0, 0],
  [0, 1, 1, 1, 1, 1, 1, 1, 1, 0],
  [0, 1, 5, 1, 1, 1, 1, 5, 1, 0],
  [0, 1, 1, 1, 1, 1, 1, 1, 1, 0],
  [0, 1, 6, 1, 1, 1, 6, 1, 1, 0],
  [0, 0, 1, 1, 1, 1, 1, 1, 0, 0],
  [0, 0, 1, 3, 3, 3, 3, 0, 0, 0],
  [0, 3, 3, 3, 3, 3, 3, 3, 0, 0],
  [0, 3, 3, 3, 3, 3, 3, 3, 0, 0],
  [1, 3, 3, 3, 3, 3, 3, 3, 1, 0],
  [1, 1, 7, 7, 7, 7, 7, 7, 1, 1],
  [0, 0, 7, 7, 7, 7, 7, 7, 0, 0],
  [0, 0, 8, 8, 8, 8, 8, 8, 0, 0],
]

function spriteForModel(model: string) {
  if (model.includes('opus')) return SPRITE_OPUS
  if (model.includes('haiku')) return SPRITE_HAIKU
  return SPRITE_SONNET
}

function hairColor(model: string): number {
  if (model.includes('opus')) return 0x1E293B
  if (model.includes('haiku')) return 0x5C3D2E
  return 0x2D1F15
}

// 에이전트별 팀 컬러 (셔츠)
const SHIRT_COLORS: Record<string, number> = Object.fromEntries(
  Object.entries(agentsConfig)
    .filter(([, a]) => (a as { shirtColor: number[] | null }).shirtColor !== null)
    .map(([id, a]) => {
      const [r, g, b] = (a as { shirtColor: number[] }).shirtColor
      return [id, (r << 16) | (g << 8) | b]
    })
)

function tieColor(agentId: string): number {
  return SHIRT_COLORS[agentId] ?? P.TIE
}

// ── 픽셀 렌더링 ───────────────────────────────────────────────
const PX = 4

function drawCharacter(
  g: Graphics,
  sprite: number[][],
  ox: number, oy: number,
  shirtCol: number,
  hairCol: number,
  tieCol: number,
  online: boolean,
) {
  const colorMap: Record<number, number> = {
    1: P.SK, 2: hairCol, 3: shirtCol, 4: P.SUIT,
    5: P.EY, 6: P.MO, 7: P.DT, 8: P.DF,
    9: P.WH, 10: tieCol, 11: P.GLS,
  }
  for (let row = 0; row < sprite.length; row++) {
    for (let col = 0; col < sprite[row].length; col++) {
      const id = sprite[row][col]
      if (id === 0) continue
      const color = colorMap[id] ?? 0xFFFFFF
      const c = online ? color : toGray(color)
      g.rect(ox + col * PX, oy + row * PX, PX, PX).fill({ color: c, alpha: online ? 1 : 0.45 })
    }
  }
}

function toGray(hex: number): number {
  const r = (hex >> 16) & 0xff
  const g = (hex >> 8) & 0xff
  const b = hex & 0xff
  const gray = Math.round(0.299 * r + 0.587 * g + 0.114 * b)
  return (gray << 16) | (gray << 8) | gray
}

// ── 직급 뱃지 색상 ────────────────────────────────────────────
const RANK_BADGE_COLORS: Record<string, { bg: number; fg: number }> = {
  '부장': { bg: 0xFDE68A, fg: 0x92400E },
  '대리': { bg: 0xBFDBFE, fg: 0x1E40AF },
  '사원': { bg: 0xE5E7EB, fg: 0x374151 },
}

// ── 3층 건물 방 배치 ─────────────────────────────────────────
interface RoomDef {
  id: string; label: string; wallColor: number; borderColor: number
  agents: string[]; col: number; floor: number; colSpan: number
}

const CHAR_W = 10 * PX   // 40
const CHAR_H = 15 * PX   // 60
const SLOT_W = CHAR_W + 55    // 95 — 넓은 오피스
const ROOM_PAD = 16
const ROW_H = CHAR_H + ROOM_PAD * 2 + 54  // 146
const FLOOR_LABEL_H = 18
const FLOOR_SEP = 6

// 밝고 화사한 오피스 톤
const ROOMS: RoomDef[] = [
  { id: 'max',        label: 'MAX 집무실',   wallColor: 0xFFFBEB, borderColor: 0xD97706,
    agents: ['MAX', 'schedule-agent'],                                      col: 0, floor: 3, colSpan: 2 },
  { id: 'quality',    label: '품질팀',       wallColor: 0xF0FDF4, borderColor: 0x16A34A,
    agents: ['nc-manager', 'qa-agent', 'issue-manager'],                    col: 0, floor: 2, colSpan: 1 },
  { id: 'dev',        label: '개발팀',       wallColor: 0xEFF6FF, borderColor: 0x2563EB,
    agents: ['dev-agent', 'crafter', 'db-manager', 'design-agent'],         col: 1, floor: 2, colSpan: 1 },
  { id: 'cs',         label: 'CS/영업팀',    wallColor: 0xFFF7ED, borderColor: 0xEA580C,
    agents: ['cs-agent', 'sales-agent'],                                    col: 0, floor: 1, colSpan: 1 },
  { id: 'management', label: '관리팀',       wallColor: 0xF5F3FF, borderColor: 0x9333EA,
    agents: ['admin-agent', 'slack-bot', 'docs-agent'],                     col: 1, floor: 1, colSpan: 1 },
]

function roomWidth(agentCount: number): number {
  return SLOT_W * agentCount + ROOM_PAD * 2 + 10
}

const COL_W = [
  Math.max(roomWidth(2), roomWidth(3)),
  Math.max(roomWidth(3), roomWidth(3)),
]
const BUILDING_W = COL_W[0] + COL_W[1] + 12
const ROOF_H = 24
const TOTAL_W = BUILDING_W + 16
const TOTAL_H = ROOF_H + (ROW_H + FLOOR_LABEL_H + FLOOR_SEP) * 3 + 20

type HoverCallback = (agentId: string | null, clientX: number, clientY: number) => void
type TapCallback   = (agentId: string, clientX: number, clientY: number) => void

// ── 가구 드로잉 함수 ──────────────────────────────────────────
function drawDesk(g: Graphics, x: number, y: number, w: number) {
  // 상판
  g.rect(x, y, w, 6).fill({ color: 0xC9956C, alpha: 0.9 })
  g.rect(x, y, w, 1).fill({ color: 0xE8C49A, alpha: 0.5 })
  // 전면 패널
  g.rect(x, y + 6, w, 9).fill({ color: 0xA0714F, alpha: 0.85 })
  // 다리
  g.rect(x + 6, y + 15, 4, 8).fill({ color: 0x8B6240, alpha: 0.8 })
  g.rect(x + w - 10, y + 15, 4, 8).fill({ color: 0x8B6240, alpha: 0.8 })
}

function drawMonitor(g: Graphics, x: number, y: number, screenColor: number) {
  // 모니터 본체
  g.rect(x, y, 16, 11).fill({ color: 0x1E293B, alpha: 0.85 })
  // 화면
  g.rect(x + 1, y + 1, 14, 9).fill({ color: screenColor, alpha: 0.55 })
  // 화면 하이라이트
  g.rect(x + 1, y + 1, 5, 2).fill({ color: 0xFFFFFF, alpha: 0.18 })
  // 스탠드
  g.rect(x + 7, y + 11, 2, 4).fill({ color: 0x334155, alpha: 0.8 })
  // 받침대
  g.rect(x + 4, y + 14, 8, 2).fill({ color: 0x334155, alpha: 0.7 })
}

function drawPlant(g: Graphics, x: number, y: number, leafColor: number) {
  // 화분
  g.rect(x + 1, y + 10, 10, 7).fill({ color: 0xC2854A, alpha: 0.85 })
  g.rect(x, y + 11, 12, 1).fill({ color: 0x9B6A35, alpha: 0.5 })
  // 잎
  g.circle(x + 6, y + 6, 6).fill({ color: leafColor, alpha: 0.75 })
  g.circle(x + 2, y + 9, 3).fill({ color: leafColor, alpha: 0.65 })
  g.circle(x + 10, y + 9, 3).fill({ color: leafColor, alpha: 0.65 })
  // 줄기
  g.rect(x + 5, y + 8, 2, 4).fill({ color: 0x4B7A32, alpha: 0.6 })
}

function drawCoffeeMachine(g: Graphics, x: number, y: number) {
  // 본체
  g.roundRect(x, y, 14, 18, 2).fill({ color: 0x475569, alpha: 0.88 })
  // 디스플레이
  g.rect(x + 2, y + 2, 10, 5).fill({ color: 0x1E40AF, alpha: 0.7 })
  g.rect(x + 2, y + 2, 4, 2).fill({ color: 0x60A5FA, alpha: 0.3 })
  // 버튼
  g.circle(x + 11, y + 4, 2).fill({ color: 0xEF4444, alpha: 0.9 })
  // 커피 추출구
  g.rect(x + 4, y + 12, 6, 4).fill({ color: 0xE7E5E4, alpha: 0.15 })
  // 스팀
  g.rect(x + 5, y - 3, 1, 4).fill({ color: 0xD1D5DB, alpha: 0.35 })
  g.rect(x + 8, y - 4, 1, 5).fill({ color: 0xD1D5DB, alpha: 0.35 })
}

// ── 창문 (밝은 버전) ──────────────────────────────────────────
function drawWindow(g: Graphics, wx: number, wy: number, accentColor: number) {
  g.rect(wx, wy, 18, 13).fill({ color: 0xBFDBFE, alpha: 0.4 })
  g.rect(wx + 1, wy + 1, 7, 11).fill({ color: 0xE0F2FE, alpha: 0.5 })
  g.rect(wx + 10, wy + 1, 7, 11).fill({ color: 0xE0F2FE, alpha: 0.5 })
  g.rect(wx, wy, 18, 1).fill({ color: accentColor, alpha: 0.5 })
  g.rect(wx, wy, 1, 13).fill({ color: accentColor, alpha: 0.5 })
  g.rect(wx + 17, wy, 1, 13).fill({ color: accentColor, alpha: 0.5 })
  g.rect(wx, wy + 12, 18, 1).fill({ color: accentColor, alpha: 0.5 })
  g.rect(wx + 8, wy, 2, 13).fill({ color: accentColor, alpha: 0.4 })
  g.rect(wx + 2, wy + 2, 2, 4).fill({ color: 0xFFFFFF, alpha: 0.25 })
}

function drawFloorLabel(_g: Graphics, x: number, y: number, label: string) {
  const style = new TextStyle({
    fontFamily: 'ui-monospace, "Cascadia Code", monospace',
    fontSize: 8,
    fill: 0x64748B,
  })
  const text = new Text({ text: label, style })
  text.x = x; text.y = y; text.alpha = 0.8
  return text
}

// ── 지붕 (따뜻한 색조) ───────────────────────────────────────
function drawRoof(g: Graphics, x: number, y: number, w: number) {
  const roofColor = 0xC4956A
  const midX = x + w / 2
  for (let row = 0; row < 6; row++) {
    const left = midX - (row + 1) * (w / 12)
    const right = midX + (row + 1) * (w / 12)
    g.rect(left, y + row * 3, right - left, 3).fill({ color: roofColor, alpha: 0.85 - row * 0.05 })
  }
  g.rect(x, y + 18, w, 4).fill({ color: 0xA07850, alpha: 0.9 })
  g.rect(midX - 1, y - 6, 2, 8).fill({ color: 0x94A3B8, alpha: 0.7 })
  g.circle(midX, y - 7, 2).fill({ color: 0xEF4444, alpha: 0.8 })
}

// ── 3층 건물 빌드 ─────────────────────────────────────────────
function buildOffice(
  app: Application,
  onlineSet: Set<string>,
  onHover: HoverCallback,
  onTap: TapCallback,
) {
  app.stage.removeChildren()

  // 하늘 배경 (밝은 그라데이션)
  const bg = new Graphics()
  for (let y = 0; y < TOTAL_H; y += 4) {
    const t = y / TOTAL_H
    const r = Math.round(0xC0 + (0xF0 - 0xC0) * t)
    const g2 = Math.round(0xD8 + (0xF4 - 0xD8) * t)
    const b = Math.round(0xF0 + (0xFC - 0xF0) * t)
    bg.rect(0, y, TOTAL_W, 4).fill({ color: (r << 16) | (g2 << 8) | b, alpha: 1 })
  }
  app.stage.addChild(bg)

  const buildingX = 8
  const buildingTopY = ROOF_H + 6

  // 건물 외벽 (따뜻한 크림)
  const buildingBg = new Graphics()
  const bh = TOTAL_H - buildingTopY - 8
  buildingBg.roundRect(buildingX, buildingTopY, BUILDING_W, bh, 4).fill({ color: 0xFAF5EE, alpha: 1 })
  buildingBg.roundRect(buildingX, buildingTopY, BUILDING_W, bh, 4).stroke({ width: 2, color: 0xD4C4A8, alpha: 0.7 })
  app.stage.addChild(buildingBg)

  // 지붕
  const roofG = new Graphics()
  drawRoof(roofG, buildingX, buildingTopY - ROOF_H + 4, BUILDING_W)
  app.stage.addChild(roofG)

  // 지면
  const ground = new Graphics()
  ground.rect(0, TOTAL_H - 8, TOTAL_W, 8).fill({ color: 0xD4C8B8, alpha: 0.9 })
  ground.rect(0, TOTAL_H - 8, TOTAL_W, 1).fill({ color: 0xB8AA98, alpha: 0.6 })
  app.stage.addChild(ground)

  const floorH = ROW_H + FLOOR_LABEL_H
  const floorY: Record<number, number> = {
    3: buildingTopY + 4,
    2: buildingTopY + 4 + floorH + FLOOR_SEP,
    1: buildingTopY + 4 + (floorH + FLOOR_SEP) * 2,
  }

  // 층 구분선
  for (let f = 1; f <= 2; f++) {
    const sepY = floorY[f + 1] + floorH
    const sep = new Graphics()
    sep.rect(buildingX + 4, sepY, BUILDING_W - 8, 1).fill({ color: 0xD4C4A8, alpha: 0.5 })
    app.stage.addChild(sep)
  }

  // 층 레이블
  for (let f = 3; f >= 1; f--) {
    const floorLabel = drawFloorLabel(new Graphics(), buildingX + 4, floorY[f] + 2, `${f}F`)
    app.stage.addChild(floorLabel)
  }

  // 방 렌더링
  for (const room of ROOMS) {
    const fy = floorY[room.floor] + FLOOR_LABEL_H
    const colGap = 4
    let rx: number
    let rw: number

    if (room.colSpan === 2) {
      rx = buildingX + 4
      rw = BUILDING_W - 8
    } else {
      rx = buildingX + 4 + room.col * (COL_W[0] + colGap)
      rw = COL_W[room.col]
    }
    const rh = ROW_H

    const rc = new Container()
    rc.x = rx; rc.y = fy
    app.stage.addChild(rc)

    // 방 배경
    const roomBg = new Graphics()
    roomBg.roundRect(0, 0, rw, rh, 4).fill(room.wallColor)
    roomBg.roundRect(0, 0, rw, rh, 4).stroke({ width: 1.5, color: room.borderColor, alpha: 0.45 })
    rc.addChild(roomBg)

    // 바닥 스트라이프
    for (let i = 1; i <= 2; i++) {
      const stripe = new Graphics()
      stripe.rect(4, rh - i * 10 - 2, rw - 8, 1).fill({ color: room.borderColor, alpha: 0.08 })
      rc.addChild(stripe)
    }

    // 창문
    const winG = new Graphics()
    drawWindow(winG, rw - 24, 4, room.borderColor)
    rc.addChild(winG)

    // 방 이름
    const labelStyle = new TextStyle({
      fontFamily: 'ui-monospace, "Cascadia Code", monospace',
      fontSize: 9,
      fill: room.borderColor,
    })
    const labelText = new Text({ text: room.label, style: labelStyle })
    labelText.x = 8; labelText.y = 4; labelText.alpha = 0.9
    rc.addChild(labelText)

    // 책상 및 가구
    const deskY = rh - ROOM_PAD - 18
    const deskG = new Graphics()
    drawDesk(deskG, 8, deskY, rw - 16)
    rc.addChild(deskG)

    // 방별 특색 가구
    const accentG = new Graphics()
    const plantY = deskY - 18
    if (room.id === 'max') {
      drawPlant(accentG, 10, plantY, 0x22C55E)
      drawPlant(accentG, rw - 24, plantY, 0x22C55E)
      drawCoffeeMachine(accentG, Math.floor(rw / 2) - 7, deskY - 20)
    } else if (room.id === 'cs') {
      drawCoffeeMachine(accentG, 10, deskY - 20)
      drawPlant(accentG, rw - 24, plantY, 0x34D399)
    } else if (room.id === 'quality') {
      drawPlant(accentG, rw - 24, plantY, 0x22C55E)
    } else if (room.id === 'dev') {
      drawPlant(accentG, rw - 24, plantY, 0x4ADE80)
      drawCoffeeMachine(accentG, 10, deskY - 20)
    } else {
      drawPlant(accentG, 10, plantY, 0x818CF8)
    }
    rc.addChild(accentG)

    // 캐릭터 배치
    const agentsList = room.agents
    const totalSlotW = agentsList.length * SLOT_W - 14
    const startX = (rw - totalSlotW) / 2

    // 캐릭터 y 위치 (책상 앞에 서 있는 형태)
    const cy = deskY - CHAR_H - 20

    // 모니터 먼저 그리기 (캐릭터 뒤에 배치)
    agentsList.forEach((agentId, idx) => {
      const online = onlineSet.has(agentId)
      const cx = startX + idx * SLOT_W
      const monX = cx + Math.floor((CHAR_W - 16) / 2)
      const screenColor = online ? (SHIRT_COLORS[agentId] ?? 0x3B82F6) : 0xCBD5E1
      const monG = new Graphics()
      drawMonitor(monG, monX, deskY - 18, screenColor)
      rc.addChild(monG)
    })

    // 캐릭터 렌더링
    agentsList.forEach((agentId, idx) => {
      const profile = AGENT_PROFILES[agentId]
      if (!profile) return

      const online = onlineSet.has(agentId)
      const sprite = spriteForModel(profile.model)
      const shirt = SHIRT_COLORS[agentId] ?? 0x6B7280
      const hair = hairColor(profile.model)
      const tie = tieColor(agentId)

      const cx = startX + idx * SLOT_W

      const charCont = new Container()
      charCont.x = cx; charCont.y = cy

      const g = new Graphics()
      drawCharacter(g, sprite, 0, 0, shirt, hair, tie, online)
      charCont.addChild(g)

      // 상태 dot
      const dot = new Graphics()
      dot.circle(CHAR_W - 3, 3, 3).fill(online ? 0x22C55E : 0xCBD5E1)
      charCont.addChild(dot)

      // 직급 뱃지 (agents.json rank 기준)
      const agentCfg = (agentsConfig as Record<string, { rank?: string | null }>)[agentId]
      const rankStr = agentCfg?.rank ?? '사원'
      const badgeColors = RANK_BADGE_COLORS[rankStr] ?? RANK_BADGE_COLORS['사원']
      const badgeW = 26
      const badgeH = 12
      const badgeX = Math.floor((CHAR_W - badgeW) / 2)
      const badgeYPos = CHAR_H + 3

      const rankBadgeBg = new Graphics()
      rankBadgeBg.roundRect(badgeX, badgeYPos, badgeW, badgeH, 2).fill(badgeColors.bg)
      charCont.addChild(rankBadgeBg)

      const rankTStyle = new TextStyle({
        fontFamily: 'ui-monospace, "Cascadia Code", monospace',
        fontSize: 7,
        fill: badgeColors.fg,
      })
      const rankTxt = new Text({ text: rankStr, style: rankTStyle })
      rankTxt.x = badgeX + 3
      rankTxt.y = badgeYPos + 2
      charCont.addChild(rankTxt)

      // 온라인 bounce 애니메이션
      if (online) {
        const phase = (idx * 0.9 + room.col * 1.3 + room.floor * 2.1)
        let t = phase
        const ticker = new Ticker()
        ticker.add(() => { t += 0.03; charCont.y = cy + Math.sin(t) * 1.5 })
        ticker.start()
        ;(charCont as unknown as { _ticker: Ticker })._ticker = ticker
      }

      charCont.eventMode = 'static'
      charCont.cursor = 'pointer'
      charCont.on('pointerover', (e) => { onHover(agentId, e.clientX, e.clientY) })
      charCont.on('pointerout',  ()  => { onHover(null, 0, 0) })
      charCont.on('pointertap',  (e) => { onTap(agentId, e.clientX, e.clientY) })

      rc.addChild(charCont)
    })
  }
}

// ── React 컴포넌트 ─────────────────────────────────────────────
interface TooltipState { id: string; x: number; y: number }

export default function OfficePage() {
  const canvasRef  = useRef<HTMLDivElement>(null)
  const outerRef   = useRef<HTMLDivElement>(null)
  const appRef     = useRef<Application | null>(null)
  const hoverRef   = useRef<HoverCallback>(() => {})
  const tapRef     = useRef<TapCallback>(() => {})

  const agents     = useAgentStore((s) => s.agents)
  const stats      = useAgentStore((s) => s.stats)
  const toolStats  = useAgentStore((s) => s.toolStats)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const [scale, setScale]     = useState(1)

  const onlineSet      = new Set(agents.filter((a) => a.online).map((a) => a.agent_id))
  const onlineCount    = onlineSet.size
  const offlineCount   = stats.total_agents - stats.online_count
  const totalToolCalls = Object.values(toolStats.by_agent).reduce((s, n) => s + n, 0)

  hoverRef.current = (agentId, x, y) => {
    if (agentId) setTooltip({ id: agentId, x, y })
    else         setTooltip(null)
  }
  tapRef.current = (agentId, x, y) => {
    setTooltip((prev) => (prev?.id === agentId ? null : { id: agentId, x, y }))
  }

  useEffect(() => {
    if (!outerRef.current) return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? outerRef.current!.clientWidth
      setScale(Math.min(1, (w - 24) / TOTAL_W))
    })
    ro.observe(outerRef.current)
    // clientWidth = content + padding(p-3: 12px*2=24px), subtract padding to get usable width
    const initW = outerRef.current.clientWidth - 24
    setScale(Math.min(1, initW / TOTAL_W))
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (!canvasRef.current) return
    const app = new Application()
    app.init({
      width: TOTAL_W, height: TOTAL_H,
      backgroundColor: 0xC0D8F0,
      antialias: false,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    }).then(() => {
      appRef.current = app
      canvasRef.current?.appendChild(app.canvas)
      buildOffice(app, onlineSet,
        (id, x, y) => hoverRef.current(id, x, y),
        (id, x, y) => tapRef.current(id, x, y),
      )
    })
    return () => { app.destroy(true); appRef.current = null }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (appRef.current)
      buildOffice(appRef.current, onlineSet,
        (id, x, y) => hoverRef.current(id, x, y),
        (id, x, y) => tapRef.current(id, x, y),
      )
  }, [agents]) // eslint-disable-line react-hooks/exhaustive-deps

  const tooltipData = tooltip
    ? (agentsConfig[tooltip.id as keyof typeof agentsConfig] as {
        name: string; emoji: string; role: string; model: string | null; rank: string | null
      } | undefined)
    : null

  return (
    <div className="p-6">
      <div className="mb-3">
        <h1 className="text-lg font-bold text-white" style={{ color: '#ffffff' }}>🏢 에이전트 오피스</h1>
        <p className="text-gray-400 text-sm mt-1">WTA AI 팀원 {Object.keys(AGENT_PROFILES).length}명 — 밝고 화사한 픽셀아트 오피스</p>
      </div>

      {/* 심플 KPI 바 */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="flex items-center gap-2 bg-gray-900 border border-gray-800 rounded-xl px-4 py-2">
          <span className="w-2 h-2 rounded-full bg-green-400" />
          <span className="text-sm text-gray-400">온라인</span>
          <span className="text-sm font-bold text-green-400">{onlineCount}</span>
        </div>
        <div className="flex items-center gap-2 bg-gray-900 border border-gray-800 rounded-xl px-4 py-2">
          <span className="w-2 h-2 rounded-full bg-gray-600" />
          <span className="text-sm text-gray-400">오프라인</span>
          <span className="text-sm font-bold text-gray-400">{offlineCount}</span>
        </div>
        <div className="flex items-center gap-2 bg-gray-900 border border-gray-800 rounded-xl px-4 py-2">
          <span className="text-sm text-gray-400">도구 호출</span>
          <span className="text-sm font-bold text-blue-400">{totalToolCalls}</span>
        </div>
        <div className="flex items-center gap-2 bg-gray-900 border border-gray-800 rounded-xl px-4 py-2">
          <span className="text-sm text-gray-400">업타임</span>
          <span className="text-sm font-bold text-purple-400">{stats.uptime}</span>
        </div>
      </div>

      {/* 직급 범례 */}
      <div className="flex flex-wrap gap-4 mb-4 text-xs text-gray-400">
        <span className="flex items-center gap-2">
          <span className="inline-block w-6 h-3 rounded" style={{ background: '#FDE68A', border: '1px solid #D97706' }} />
          부장
        </span>
        <span className="flex items-center gap-2">
          <span className="inline-block w-6 h-3 rounded" style={{ background: '#BFDBFE', border: '1px solid #3B82F6' }} />
          대리
        </span>
        <span className="flex items-center gap-2">
          <span className="inline-block w-6 h-3 rounded" style={{ background: '#E5E7EB', border: '1px solid #9CA3AF' }} />
          사원
        </span>
        <span className="text-gray-600 hidden sm:inline">• 캐릭터를 탭/호버하면 정보 표시</span>
      </div>

      {/* 캔버스 — position:absolute로 canvasRef를 flow에서 제거해 모바일 가로 overflow 방지 */}
      <div ref={outerRef} className="bg-sky-50 rounded-2xl border border-gray-200 p-3 w-full overflow-hidden">
        <div style={{ position: 'relative', width: TOTAL_W * scale, height: TOTAL_H * scale }}>
          <div
            ref={canvasRef}
            className="rounded-xl overflow-hidden"
            style={{ position: 'absolute', top: 0, left: 0, transformOrigin: 'top left', transform: `scale(${scale})` }}
          />
        </div>
      </div>

      {/* 에이전트 현황 */}
      <div className="mt-4 flex flex-wrap gap-2">
        {Object.entries(AGENT_PROFILES).map(([id, p]) => {
          const online = onlineSet.has(id)
          const shirt = SHIRT_COLORS[id] ?? 0x6b7280
          const hex = `#${shirt.toString(16).padStart(6, '0')}`
          return (
            <div
              key={id}
              className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg border ${
                online ? 'border-gray-700 text-gray-300' : 'border-gray-800 text-gray-600'
              }`}
            >
              <span className="w-2 h-2 rounded-full" style={{ background: online ? hex : '#374151' }} />
              {p.emoji} {p.name}
            </div>
          )
        })}
      </div>

      {/* 툴팁 */}
      {tooltip && tooltipData && (
        <div
          style={{ position: 'fixed', left: tooltip.x + 14, top: tooltip.y - 10, zIndex: 50 }}
          className="pointer-events-none bg-gray-900 border border-gray-700 rounded-xl p-3 shadow-2xl min-w-[160px]"
        >
          <div className="text-white font-semibold text-sm mb-1">
            {tooltipData.emoji} {tooltipData.name}
          </div>
          <div className="text-gray-400 text-xs mb-1 leading-snug">{tooltipData.role}</div>
          <div className="text-gray-600 text-xs font-mono">{tooltipData.model ?? '—'}</div>
          {tooltipData.rank && (
            <div className="mt-1.5">
              <span className="px-1.5 py-0.5 rounded text-xs bg-gray-800 text-gray-400">
                {tooltipData.rank}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
