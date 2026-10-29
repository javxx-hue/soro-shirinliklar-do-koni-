"""
Google Gemini AI sweet consultant ("Shirinlik Somelyesi") service.
Provides grounded sweet recommendations strictly anchored to products in stock,
with resilient heuristic fallback when API key is missing or network/quota fails.
Formats all output in clean Telegram HTML without asterisks (*).
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def format_ai_response_to_html(raw_text: str) -> str:
    """
    Cleans and converts raw AI response (which may contain markdown like **bold**, *italic*,
    and bullet points) into clean, elegant Telegram-compatible HTML without asterisks.
    Also protects and properly escapes raw angle brackets to prevent HTML parsing errors.
    """
    if not raw_text:
        return ""
    text = raw_text.strip()

    # 1. Convert markdown headers: ### Header -> <b>Header</b>
    text = re.sub(r"^(?:#{1,6})\s*(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # 2. Convert bold: **text** -> <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # 3. Convert bullet list items at start of lines: * item or - item -> • item
    text = re.sub(r"^\s*[\*\-]\s+", r"• ", text, flags=re.MULTILINE)

    # 4. Convert italic: *text* -> <i>text</i>
    text = re.sub(r"(?<!\*)\*([^\*\n]+?)\*(?!\*)", r"<i>\1</i>", text)

    # 5. Remove any leftover asterisks (which look like markdown artifacts)
    text = text.replace("*", "")

    # 6. Escape raw angle brackets that are not part of valid Telegram HTML tags
    placeholders: List[str] = []

    def _save_tag(m: re.Match) -> str:
        placeholders.append(m.group(0))
        return f"___HTML_TAG_{len(placeholders) - 1}___"

    tag_pattern = re.compile(
        r"</?(?:b|i|u|s|code|pre|blockquote)>|<a\s+href=\"[^\"]+\">|</a>",
        re.IGNORECASE,
    )
    text = tag_pattern.sub(_save_tag, text)

    # Escape any remaining raw & < >
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Restore saved valid tags
    for idx, tag in enumerate(placeholders):
        text = text.replace(f"___HTML_TAG_{idx}___", tag)

    # Clean up excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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

ПРАВИЛА ОФОРМЛЕНИЯ СООБЩЕНИЙ:
- НИКОГДА не используй звездочки (*) или (**) для выделения! Звездочки строго запрещены.
- Для выделения жирным используй тег <b>текст</b>, для курсива <i>текст</i>.
- Для пунктов списков используй эмодзи (✨, 🍰, 🔸, •), но ни в коем случае не символы * или -.

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
5. Javobingizni o'zbek tilida, ishtahani ochuvchi, iliq, samimiy va chiroyli tartiblangan shaklda yozing. 🍰, ✨, 🎂, ☕️ kabi mos emojilardan foydalaning.

MATN FORMATLASH QOIDALARI:
- HECH QACHON matnda yulduzcha (*) yoki (**) belgilarini ishlatmang! Yulduzchalar butunlay taqiqlangan.
- Qalin yozuvlar uchun <b>matn</b> tegidan, kursiv uchun <i>matn</i> tegidan foydalaning.
- Ro'yxat bandlari uchun chiroyli emojilardan (✨, 🍰, 🔸, •) foydalaning, hech qachon * yoki - belgilari bilan boshlamang.

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

    # Format localized response without asterisks
    if user_lang == "ru":
        lines = [
            "🍰 <b>Рекомендация Сладкого Сомелье:</b>\n",
            "Для вашего прекрасного чаепития или праздника идеально подойдут следующие десерты из нашего меню:\n",
        ]
        for p in top_matches:
            name = p.get("name_ru") or p.get("name_uz") or p.get("name", "")
            desc = p.get("description_ru") or p.get("description_uz") or ""
            weight = p.get("weight") or ""
            price = p.get("price", 0)
            formatted_price = f"{price:,}".replace(",", " ")

            lines.append(f"✨ <b>{name}</b>")
            if desc:
                lines.append(f"📝 {desc}")
            if weight:
                lines.append(f"⚖️ Вес: <b>{weight}</b>")
            lines.append(f"💰 Цена: <b>{formatted_price} сум</b>\n")

        lines.append("Прекрасно сочетается с ароматным чаем или кофе! ☕️")
        lines.append("Чтобы оформить заказ, нажмите кнопку «Vitrinani ko'rish» ниже.")
        return format_ai_response_to_html("\n".join(lines))

    lines = [
        "🍰 <b>Shirinlik Somelyesi tavsiyasi:</b>\n",
        "Sizning xohishingiz va maroqli choyxo'rligingiz uchun bizning vitrinamizdan quyidagi nozik shirinliklarni tavsiya qilaman:\n",
    ]
    for p in top_matches:
        name = p.get("name_uz") or p.get("name_ru") or p.get("name", "")
        desc = p.get("description_uz") or p.get("description_ru") or ""
        weight = p.get("weight") or ""
        price = p.get("price", 0)
        formatted_price = f"{price:,}".replace(",", " ")

        lines.append(f"✨ <b>{name}</b>")
        if desc:
            lines.append(f"📝 {desc}")
        if weight:
            lines.append(f"⚖️ Vazni: <b>{weight}</b>")
        lines.append(f"💰 Narxi: <b>{formatted_price} so'm</b>\n")

    lines.append("Har bir shirinligimiz tabiiy masalliqlardan mehr bilan tayyorlangan! ☕️")
    lines.append("Buyurtma berish uchun quyidagi «Vitrinani ko'rish» tugmasini bosing.")
    return format_ai_response_to_html("\n".join(lines))


async def get_sweet_recommendation(
    user_prompt: str,
    available_products: List[Dict[str, Any]],
    user_lang: str = "uz",
    api_key: str = "",
    model_name: str = "gemini-3.5-flash-lite",
) -> str:
    """
    Generates grounded AI sweet recommendation using Google Gemini API.
    If api_key is missing or API call fails, seamlessly falls back to heuristic recommendation.
    Formats output as clean, asterisk-free Telegram HTML.
    """
    if not api_key or not api_key.strip():
        logger.info("Gemini API key is not configured; using heuristic sweet recommendation.")
        return fallback_sweet_recommendation(user_prompt, available_products, user_lang)

    # Models to try in order of preference
    preferred_models = [model_name]
    for candidate in ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]:
        if candidate not in preferred_models:
            preferred_models.append(candidate)

    system_instruction = build_grounded_system_prompt(available_products, user_lang)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key.strip())
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        )

        last_error = None
        for candidate_model in preferred_models:
            try:
                call_coro = client.aio.models.generate_content(
                    model=candidate_model,
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
                    return format_ai_response_to_html(cleaned)
                logger.warning("Model %s returned empty text, trying next...", candidate_model)
            except Exception as e:
                last_error = e
                logger.warning("Model %s failed: %s (%s)", candidate_model, type(e).__name__, e)
                continue

        logger.warning(
            "All Gemini candidate models failed (last error: %s); falling back to heuristic engine.",
            last_error,
        )
        return fallback_sweet_recommendation(user_prompt, available_products, user_lang)

    except Exception as e:
        logger.warning(
            "Gemini sweet recommendation setup failed (%s: %s); gracefully falling back to heuristic engine.",
            type(e).__name__,
            e,
        )
        return fallback_sweet_recommendation(user_prompt, available_products, user_lang)
