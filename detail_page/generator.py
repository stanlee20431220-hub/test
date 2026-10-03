"""상세페이지 문구 생성기.

ANTHROPIC_API_KEY 가 있으면 Claude 로 문구를 만들고,
없거나 실패하면 규칙 기반(템플릿) 문구로 대신합니다.
"""
import json
import os
import re

import requests

TONES = {
    "friendly": "친근하고 발랄한 말투",
    "premium": "고급스럽고 절제된 말투",
    "trust": "신뢰감 있고 정보 위주의 말투",
}

API_URL = "https://api.anthropic.com/v1/messages"


class GenerationError(Exception):
    pass


def parse_lines(text):
    return [ln.strip(" -•\t") for ln in (text or "").splitlines() if ln.strip(" -•\t")]


def parse_specs(text):
    specs = []
    for line in parse_lines(text):
        parts = re.split(r"\s*[:：]\s*", line, maxsplit=1)
        if len(parts) == 2:
            specs.append({"k": parts[0], "v": parts[1]})
    return specs


def generate_content(product):
    """product dict -> content dict. 두 번째 값은 사용된 방식('ai'|'template')."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            return _generate_with_claude(product, api_key), "ai"
        except GenerationError:
            pass
    return _generate_with_template(product), "template"


def _generate_with_claude(product, api_key):
    tone = TONES.get(product.get("tone"), TONES["friendly"])
    prompt = f"""한국 오픈마켓(스마트스토어/쿠팡) 상품 상세페이지 문구를 작성하세요. 말투: {tone}.

상품명: {product['name']}
카테고리: {product.get('category', '')}
가격: {product.get('price', '')}
타깃 고객: {product.get('target', '')}
핵심 특징:
{chr(10).join('- ' + f for f in product.get('features', []))}

입력되지 않은 수치·인증·효능은 절대 지어내지 마세요. 아래 JSON 하나만 출력하세요(설명 금지):
{{"headline": "한 줄 핵심 카피", "subheadline": "보조 문구",
 "pains": ["고객 고민 3개"],
 "features": [{{"title": "특징 제목", "desc": "2~3문장 설명"}}],
 "faqs": [{{"q": "질문", "a": "답변"}}],
 "cta": "구매 유도 문구"}}
features 는 입력된 핵심 특징 개수만큼, faqs 는 3개."""
    try:
        resp = requests.post(
            API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"]
        match = re.search(r"\{.*\}", text, re.S)
        data = json.loads(match.group(0))
    except (requests.RequestException, KeyError, IndexError, AttributeError, ValueError) as exc:
        raise GenerationError(str(exc)) from exc

    return {
        "headline": str(data.get("headline", product["name"])),
        "subheadline": str(data.get("subheadline", "")),
        "pains": [str(p) for p in data.get("pains", [])][:5],
        "features": [
            {"title": str(f.get("title", "")), "desc": str(f.get("desc", ""))}
            for f in data.get("features", [])
            if isinstance(f, dict)
        ],
        "specs": product.get("specs", []),
        "faqs": [
            {"q": str(f.get("q", "")), "a": str(f.get("a", ""))}
            for f in data.get("faqs", [])
            if isinstance(f, dict)
        ],
        "notice": product.get("notice", ""),
        "cta": str(data.get("cta", "지금 바로 만나보세요")),
    }


def _generate_with_template(product):
    name = product["name"]
    target = product.get("target") or "꼼꼼하게 고르는 분"
    tone = product.get("tone", "friendly")
    feats = product.get("features") or ["꼼꼼한 품질 관리", "합리적인 가격", "빠른 배송"]

    headline = {
        "friendly": f"{name}, 한 번 써보면 알아요!",
        "premium": f"{name}, 차이는 디테일에서 시작됩니다",
        "trust": f"{name} — 꼭 필요한 기능만 담았습니다",
    }.get(tone, name)
    cta = {
        "friendly": "지금 바로 만나보세요!",
        "premium": "특별한 선택을 시작하세요",
        "trust": "상세 정보를 확인하고 구매하세요",
    }.get(tone, "지금 바로 만나보세요")

    return {
        "headline": headline,
        "subheadline": f"{target}을 위해 준비했습니다.",
        "pains": [
            f"{product.get('category') or '상품'}, 어떤 걸 골라야 할지 고민되셨나요?",
            "후기는 많은데 정작 믿을 만한 정보가 없어 답답하셨나요?",
            "가격 대비 만족스러운 제품을 찾고 계셨나요?",
        ],
        "features": [
            {"title": f, "desc": f"{name}의 핵심 포인트, '{f}'. 사용하는 순간 차이를 느껴보세요."}
            for f in feats
        ],
        "specs": product.get("specs", []),
        "faqs": [
            {"q": "배송은 얼마나 걸리나요?", "a": "결제 완료 후 영업일 기준 1~3일 내 출고됩니다."},
            {"q": "교환/반품이 가능한가요?", "a": "수령 후 7일 이내 미사용 상품에 한해 가능합니다."},
            {"q": f"{name}은 누구에게 추천하나요?", "a": f"{target}에게 추천드립니다."},
        ],
        "notice": product.get("notice", ""),
        "cta": cta,
    }
