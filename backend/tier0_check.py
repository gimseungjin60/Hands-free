"""
Tier0 시나리오 검증 하니스 (오디오 없이 추론+함수콜 경로만).

실행: backend/.env 에 OPENAI_API_KEY 설정 후
    python tier0_check.py

각 시나리오에서 get_part_info 가 실제로 호출되는지(환각 방지)와
핵심 사실이 답변에 들어가는지 확인한다.
"""
import part_info
from voice_agent import VoiceAgent

# (질문, 답에 들어가야 할 핵심 단서들 — 하나라도 있으면 통과로 간주)
SCENARIOS = [
    ("R5 자리 저항 뭐야?",        [["10k", "10킬로", "10 킬로"]]),
    ("이 LED 긴 다리 어디로 가?", [["긴 다리", "긴다리"], ["+", "플러스", "애노드"]]),
    ("전해 콘덴서 방향 알려줘",    [["짧은 다리", "짧은다리", "흰 띠", "흰띠"], ["-", "마이너스", "음극"]]),
]


def main():
    part_info.load_board()
    agent = VoiceAgent()

    # get_part_info 호출 추적 (환각 방지 검증)
    called = []
    orig = part_info.get_part_info
    def traced(ref):
        called.append(ref)
        return orig(ref)
    part_info.get_part_info = traced
    import voice_agent as va
    va.get_part_info = traced

    passed = 0
    for q, groups in SCENARIOS:
        called.clear()
        ans = agent.get_response(q)
        ok = all(any(c in ans for c in grp) for grp in groups)
        print(f"\nQ: {q}")
        print(f"   조회: {called or '(없음)'}")
        print(f"A: {ans}")
        print(f"   → {'✅ PASS' if ok else '❌ FAIL'}")
        passed += ok

    print(f"\n==== Tier0: {passed}/{len(SCENARIOS)} 통과 ====")


if __name__ == "__main__":
    main()
