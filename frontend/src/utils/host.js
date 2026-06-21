/**
 * 백엔드 호스트 결정 헬퍼. (senior-smile-project utils/host.js 재사용·일반화)
 *
 * - 로컬 개발(npm run dev): http://<hostname>:8000 자동 라우팅
 *     태블릿이 PC IP로 접속하든 PC 브라우저든 동일하게 동작(음성 e2e).
 * - 프로덕션 빌드: VITE_BACKEND_URL(.env)로 고정. https → WS는 wss 자동 승격.
 */

const BACKEND_PORT = 8000

const PROD_BACKEND = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/+$/, '')

function _hostname() {
  if (typeof window === 'undefined') return 'localhost'
  return window.location.hostname || 'localhost'
}

function _httpBase() {
  if (import.meta.env.PROD && PROD_BACKEND) return PROD_BACKEND
  // 프로덕션이라도 VITE_BACKEND_URL 미설정이면 동일 출처(백엔드가 dist 서빙) 사용
  if (import.meta.env.PROD) return ''
  return `http://${_hostname()}:${BACKEND_PORT}`
}

/** 백엔드 HTTP 베이스 URL */
export function httpUrl() {
  return _httpBase()
}

/** 백엔드 WebSocket URL. http→ws, https→wss 자동 치환 */
export function wsUrl(path = '') {
  const base = _httpBase()
  if (base) return `${base.replace(/^http/, 'ws')}${path}`
  // 동일 출처: 현재 origin 기준
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}${path}`
}
