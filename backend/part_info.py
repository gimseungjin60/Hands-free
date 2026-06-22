"""지식베이스 로더 + get_part_info (환각 방지용 정확값 조회).

보드 데이터(board_*.json)를 엔진과 분리한다.
- 지금은 단일 보드 → 전체 meta 를 컨텍스트로 주입(board_context)하고, 정확한 부품 값은
  function calling(get_part_info)으로 조회한다.
- 나중에 보드가 늘면 이 모듈만 RAG 조회로 바꾸면 됨(엔진/프롬프트 불변).
"""
from __future__ import annotations

import re
import json
from pathlib import Path

import config

_board = None


def load_board(path: str | None = None) -> dict:
    global _board
    p = Path(path or config.BOARD_FILE)
    _board = json.loads(p.read_text(encoding="utf-8"))
    return _board


def get_board() -> dict:
    if _board is None:
        load_board()
    return _board


def _norm(ref: str) -> str:
    """레퍼런스 정규화: 대문자 + 영숫자만 ('r 5', 'R-5' → 'R5')."""
    return re.sub(r"[^A-Z0-9]", "", (ref or "").upper())


def get_part_info(reference: str) -> dict:
    """부품 레퍼런스(예: R5, D1, C2, U4, AR1, TR5)로 정확한 값·극성·색띠·위치·조립순서 조회.
    값/극성/위치를 답하기 전 반드시 호출. 못 찾으면 found=False — 절대 추측하지 말 것."""
    board = get_board()
    parts = board["parts"]
    key = _norm(reference)

    part = parts.get(key)
    if part is None:
        for k, v in parts.items():
            if _norm(k) == key:
                part = v
                key = k
                break

    if part is None:
        return {
            "found": False,
            "reference": reference,
            "message": f"'{reference}' 부품을 보드 데이터에서 못 찾음. 추측하지 말고 모른다고 답할 것.",
        }

    result = {"found": True, "reference": key}
    result.update(part)

    meta = board.get("meta", {})
    if part.get("type") == "resistor":
        rmeta = meta.get("resistor", {})
        result["read_direction"] = rmeta.get("read_direction")
        result["tolerance"] = rmeta.get("tolerance_band")
        if part.get("polarity") is False:
            result["polarity_note"] = meta.get("common_warnings", {}).get("resistor_direction")

    env = part.get("envelope")
    if env is not None:
        result["envelope_desc"] = board.get("envelopes", {}).get(str(env))

    return result


def board_context() -> str:
    """단일 보드 컨텍스트 주입용 요약(meta + 레퍼런스 목록). 정확한 값은 get_part_info로 조회."""
    board = get_board()
    meta = board.get("meta", {})
    r = meta.get("resistor", {})
    warns = meta.get("common_warnings", {})

    color = r.get("color_to_digit", {})
    mult = r.get("multiplier_band", {})
    refs = ", ".join(board.get("parts", {}).keys())
    envs = board.get("envelopes", {})

    lines = [
        f"[보드] {board.get('board')} (MCU {board.get('mcu')})",
        "[저항 색띠] " + " · ".join(f"{c}{d}" for c, d in color.items()),
        "[배수 띠] " + " · ".join(f"{c}×{m}" for c, m in mult.items()),
        f"[읽는 방향] {r.get('read_direction')}",
        f"[헷갈림] {r.get('ambiguous_note')}",
        "[극성/방향 경고]",
        f"  · LED: {warns.get('led')}",
        f"  · 전해 콘덴서: {warns.get('electrolytic')}",
        f"  · 다이오드: {warns.get('diode')}",
        f"  · IC/EEPROM: {warns.get('ic')}",
        f"  · 어레이저항: {warns.get('array_resistor')}",
        f"  · 트랜지스터: {warns.get('transistor')}",
        f"[조회 가능한 레퍼런스] {refs}",
        "[봉투(조립 순서) — '다음 봉투'·'N번 봉투' 질문에 직접 답하라]",
        *[f"  · 봉투 {k}: {v}" for k, v in sorted(envs.items())],
    ]
    return "\n".join(lines)
