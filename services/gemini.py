"""
Google Gemini AI sweet consultant ("Shirinlik Somelyesi") service.
Provides grounded sweet recommendations strictly anchored to products in stock,
with resilient heuristic fallback when API key is missing or network/quota fails.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def build_grounded_system_prompt(
    available_products: List[Dict[str, Any]],
    user_lang: str = "uz",
) -> str:
    """
    Builds strict grounding system instructions containing the live catalogue of available products.
    Instructs the AI sommelier to recommend ONLY from the provided list, never hallucinating items.
    """
    catalog_lines = []
    for p in available_products:
        p_id = p.get("id")
        name_uz = p.get("name_uz") or p.get("name", "")
        name_ru = p.get("name_ru") or name_uz
        desc_uz = p.get("description_uz") or ""
        desc_ru = p.get("description_ru") or desc_uz
        price = p.get("price", 0)
        formatted_price = f"{price:,}".replace(",", " ")
        weight = p.get("weight") or "N/A"

        catalog_lines.append(
            f"- [ID {p_id}] UZ: {name_uz} | RU: {name_ru} | Vazn/Вес: {weight} | "
            f"Narxi/Цена: {formatted_price} so'm | "
            f"Tavsif (UZ): {desc_uz} | Описание (RU): {desc_ru}"
        )

    catalog_str = "\n".join(catalog_lines) if catalog_lines else "(Hozirda mahsulotlar ro'yxati bo'sh)"

    if user_lang == "ru":
        return f"""Ты — «Сладкий Сомелье» (Shirinlik Somelyesi), экспертный кондитерский консультант кондитерского дома «SORO Shirinliklari (Самарканд)».
Твоя цель — помочь гостю выбрать идеальный десерт к свадьбе, торжеству, чаепитию или семейному празднику.
Магазин расположен в Самарканде (Вокзал, ориентир ресторан «Saodat»), доставка по Самарканду бесплатная!

СТРОГИЕ ПРАВИЛА ЗАЗЕМЛЕНИЯ (GROUNDING):
1. Ты имеешь право рекомендовать ИСКЛЮЧИТЕЛЬНО сладости из списка доступных товаров ниже.
2. НИКОГДА не выдумывай и не предлагай десерты, вкусы, начинки или цены, которых нет в этом списке.
3. Если гость просит то, чего нет в меню, вежливо объясни это и предложи наиболее близкую альтернативу из списка.
4. Всегда указывай точные цены и вес десертов так, как они указаны в списке.
5. Отвечай аппетитно, тепло, вежливо и лаконично на русском языке. Используй эмодзи 🍰, ✨, ☕️.

СПИСОК ДОСТУПНЫХ ТОВАРОВ В НАЛИЧИИ:
{catalog_str}
"""

    return f"""Siz — «Shirinlik Somelyesi», Samarqand shahridagi mashhur «SORO Shirinliklari» qandolat uyining shaxsiy aqlli maslahatchisisiz.
Sizning vazifangiz — xaridorga to'y, marosim, tug'ilgan kun, choyxo'rlik yoki oilaviy bayramlar uchun eng ajoyib shirinlik va tortlarni tanlashda samimiy yordam berish.
Do'konimiz Samarqand shahri, Vagzal ("Saodat" restorani)da joylashgan, Samarqand bo'ylab yetkazib berish bepul!

QAT'IY QOIDALAR (STRICT GROUNDING):
1. Siz FAQAT va FAQAT quyida keltirilgan mavjud mahsulotlar ro'yxatidagi shirinliklarni tavsiya qilishingiz shart.
2. Ro'yxatda mavjud bo'lmagan tort, pishiriq, ichimlik yoki masalliqlarni aslo o'ylab topmang (hallucination qilmang).
3. Agar mijoz ro'yxatda yo'q narsani so'rasa, xushmuomalalik bilan tushuntiring va katalogimizdagi eng yaqin va mos keladigan shirinlikni tavsiya qiling.
4. Mahsulotlarning narxi va vaznini ro'yxatdagi kabi aniq ko'rsating.
5. Javobingizni o'zbek tilida, ishtahani ochuvchi, iliq, madaniyatli va ixcham shaklda yozing. 🍰, ✨, 🎂, ☕️ kabi mos emojilardan foydalaning.

MAVJUD MAHSULOTLAR RO'YXATI:
{catalog_str}
"""


def fallback_sweet_recommendation(
    user_prompt: str,
    available_products: List[Dict[str, Any]],
    user_lang: str = "uz",
) -> str:
    """
    Heuristic rule-based recommendation engine that analyzes user query keywords
    and selects best-matching products from the live database.
    Used when Gemini API key is not configured or external service is unreachable.
    """
    if not available_products:
        if user_lang == "ru":
            return (
                "🍰 К сожалению, в данный момент в наличии нет доступных десертов. "
                "Наши шеф-кондитеры уже выпекают свежую партию! Загляните в каталог чуть позже."
            )
        return (
            "🍰 Afsuski, hozirda do'konimiz vitrinasida mavjud shirinliklar qolmagan. "
            "Qandolatchilarimiz tez orada yangi va issiq shirinliklarni pishirib qo'yishadi! "
            "Katalogimizni birozdan so'ng tekshirib ko'ring."
        )

    q = (user_prompt or "").strip().lower()

    # Thematic keyword groups
    theme_keywords = {
        "chocolate": [
            "shokolad", "шоколад", "choc", "kakao", "какао", "brauni", "брауни",
            "ganash", "ганаш", "truffle", "trufel", "трюфел",
        ],
        "cake": [
            "tort", "торт", "biskvit", "бисквит", "medovik", "медовик",
            "napoleon", "наполеон", "чизкейк", "cheesecake",
        ],
        "fruit_light": [
            "meva", "mevali", "qulupnay", "malina", "rezavor", "yengil",
            "kam kalor", "parhez", "диет", "фрукт", "ягод", "клубник",
            "малин", "легк", "нежн", "творог", "limon", "лимон",
        ],
        "pastry_cupcake": [
            "kapkeyk", "pirojniy", "keks", "ekler", "трайфл", "макарон",
            "macaron", "капкейк", "пирожн", "кекс", "эклер", "desert", "десерт",
        ],
        "event_kids": [
            "bayram", "tug'ilgan", "to'y", "tadbir", "bola", "bolalar",
            "yubiley", "mehmon", "праздник", "день рождени", "юбилей",
            "дет", "ребенок", "детск",
        ],
    }

    # Identify which themes the user asked for
    active_themes = set()
    for theme, kw_list in theme_keywords.items():
        if any(kw in q for kw in kw_list):
            active_themes.add(theme)

    scored_products = []
    tokens = [t for t in re.split(r"\W+", q) if len(t) >= 3]

    for p in available_products:
        score = 0
        name_uz = (p.get("name_uz") or "").lower()
        name_ru = (p.get("name_ru") or "").lower()
        desc_uz = (p.get("description_uz") or "").lower()
        desc_ru = (p.get("description_ru") or "").lower()
        combined_text = f"{name_uz} {name_ru} {desc_uz} {desc_ru}"

        # Direct token match
        for tok in tokens:
            if tok in name_uz or tok in name_ru:
                score += 8
            elif tok in desc_uz or tok in desc_ru:
                score += 4

        # Thematic alignment match
        for theme in active_themes:
            kws = theme_keywords[theme]
            if any(kw in combined_text for kw in kws):
                score += 10

        scored_products.append((score, p))

    # Sort descending by score
    scored_products.sort(key=lambda item: item[0], reverse=True)

    # Pick top matches (up to 2-3 products)
    top_matches = [p for score, p in scored_products if score > 0][:3]
    if not top_matches:
        top_matches = available_products[:2]

    # Format localized response
    if user_lang == "ru":
        lines = [
            "🍰 **Рекомендация Сладкого Сомелье:**\n",
            "Для вашего прекрасного чаепития или праздника идеально подойдут следующие десерты из нашего меню:\n",
        ]
        for p in top_matches:
            name = p.get("name_ru") or p.get("name_uz") or p.get("name", "")
            desc = p.get("description_ru") or p.get("description_uz") or ""
            weight = p.get("weight") or ""
            price = p.get("price", 0)
            formatted_price = f"{price:,}".replace(",", " ")

            lines.append(f"✨ **{name}**")
            if desc:
                lines.append(f"📝 {desc}")
            if weight:
                lines.append(f"⚖️ Вес: {weight}")
            lines.append(f"💰 Цена: {formatted_price} сум\n")

        lines.append("Прекрасно сочетается с ароматным чаем или кофе! ☕️")
        lines.append("Чтобы оформить заказ, нажмите кнопку «Vitrinani ko'rish» ниже.")
        return "\n".join(lines)

    lines = [
        "🍰 **Shirinlik Somelyesi tavsiyasi:**\n",
        "Sizning xohishingiz va maroqli choyxo'rligingiz uchun bizning vitrinamizdan quyidagi nozik shirinliklarni tavsiya qilaman:\n",
    ]
    for p in top_matches:
        name = p.get("name_uz") or p.get("name_ru") or p.get("name", "")
        desc = p.get("description_uz") or p.get("description_ru") or ""
        weight = p.get("weight") or ""
        price = p.get("price", 0)
        formatted_price = f"{price:,}".replace(",", " ")

        lines.append(f"✨ **{name}**")
        if desc:
            lines.append(f"📝 {desc}")
        if weight:
            lines.append(f"⚖️ Vazni: {weight}")
        lines.append(f"💰 Narxi: {formatted_price} so'm\n")

    lines.append("Har bir shirinligimiz tabiiy masalliqlardan mehr bilan tayyorlangan! ☕️")
    lines.append("Buyurtma berish uchun quyidagi «Vitrinani ko'rish» tugmasini bosing.")
    return "\n".join(lines)


async def get_sweet_recommendation(
    user_prompt: str,
    available_products: List[Dict[str, Any]],
    user_lang: str = "uz",
    api_key: str = "",
    model_name: str = "gemini-2.5-flash",
) -> str:
    """
    Generates grounded AI sweet recommendation using Google Gemini API.
    If api_key is missing or API call fails, seamlessly falls back to heuristic recommendation.
    """
    if not api_key or not api_key.strip():
        logger.info("Gemini API key is not configured; using heuristic sweet recommendation.")
        return fallback_sweet_recommendation(user_prompt, available_products, user_lang)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key.strip())
        system_instruction = build_grounded_system_prompt(available_products, user_lang)

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        )

        call_coro = client.aio.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=config,
        )

        if inspect.isawaitable(call_coro):
            response = await asyncio.wait_for(call_coro, timeout=30.0)
        else:
            response = call_coro

        text = getattr(response, "text", "") or ""
        cleaned = text.strip()
        if cleaned:
            return cleaned

        logger.warning("Gemini returned empty recommendation text; falling back to heuristic.")
        return fallback_sweet_recommendation(user_prompt, available_products, user_lang)

    except Exception as e:
        logger.warning(
            "Gemini sweet recommendation failed (%s: %s); gracefully falling back to heuristic engine.",
            type(e).__name__,
            e,
        )
        return fallback_sweet_recommendation(user_prompt, available_products, user_lang)
