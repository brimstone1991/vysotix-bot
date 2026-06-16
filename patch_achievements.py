# ================================================================
# ПАТЧ: интеграция достижений в main.py
# Применяй изменения по одному блоку
# ================================================================

# ── 1. ИМПОРТ ──────────────────────────────────────────────────
# Добавь в самый верх main.py, после остальных импортов:

from achievements import check_achievements, achievements_card, format_new_achievements


# ── 2. КНОПКА В МЕНЮ (child) ───────────────────────────────────
# В функции show_menu(), в блоке else (role != "parent"),
# замени строку с кнопками "Магазин наград" / "Босс рейд":
#
# БЫЛО:
#   [InlineKeyboardButton("🛒 Магазин наград", callback_data="shop"),
#    InlineKeyboardButton("⚔️ Босс рейд", callback_data="boss")],
#
# СТАЛО:
#   [InlineKeyboardButton("🛒 Магазин наград", callback_data="shop"),
#    InlineKeyboardButton("⚔️ Босс рейд", callback_data="boss")],
#   [InlineKeyboardButton("🏅 Достижения", callback_data="achievements")],


# ── 3. КНОПКА В МЕНЮ (parent) ──────────────────────────────────
# В блоке if role == "parent", добавь кнопку после "⚔️ Босс рейд":
#   kb.append([InlineKeyboardButton("🏅 Достижения", callback_data="achievements")])


# ── 4. КНОПКА В ПРОФИЛЕ ────────────────────────────────────────
# В handle_callback, блок data == "profile", замените kb:
#
# БЫЛО:
#   kb = [[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
#
# СТАЛО:
#   kb = [
#       [InlineKeyboardButton("🏅 Достижения", callback_data="achievements")],
#       [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
#   ]


# ── 5. ОБРАБОТЧИК ДОСТИЖЕНИЙ ───────────────────────────────────
# Добавь в handle_callback, в любом месте среди if data == ...:

"""
    if data == "achievements":
        reset_daily_tasks(user)
        save_users(users)
        kb = [[InlineKeyboardButton("◀️ Назад", callback_data="profile")]]
        await query.edit_message_text(
            achievements_card(user),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return
"""


# ── 6. ПРОВЕРКА ПРИ ВЫПОЛНЕНИИ СВОЕГО ЗАДАНИЯ ──────────────────
# В handle_callback, блок data.startswith("done_"),
# ПОСЛЕ строки `save_users(users)` и ПЕРЕД формированием msg:
#
# БЫЛО:
#   save_users(users)
#   attr = ATTRS[task["attr"]]
#   msg = (...)
#
# СТАЛО:
#   new_achs = check_achievements(user)
#   save_users(users)
#   attr = ATTRS[task["attr"]]
#   msg = (...)
#   # В конце msg добавь:
#   msg += format_new_achievements(new_achs)


# ── 7. ПРОВЕРКА ПРИ ВЫПОЛНЕНИИ НАЗНАЧЕННОГО ЗАДАНИЯ ────────────
# Аналогично в блоке data.startswith("adone_"):
#
# ПОСЛЕ строки `boss_msg = await apply_boss_damage(...)`
# и ПЕРЕД `save_users(users)`:
#
#   new_achs = check_achievements(user)
#   save_users(users)
#   ...
#   msg += format_new_achievements(new_achs)


# ── 8. ПРОВЕРКА ПРИ ПОКУПКЕ В МАГАЗИНЕ ─────────────────────────
# В handle_buy(), ПЕРЕД save_users(users):
#
#   new_achs = check_achievements(user)
#   save_users(users)


# ── 9. ПРОВЕРКА ПРИ ВСТУПЛЕНИИ В ОТРЯД ────────────────────────
# В handle_callback, блоке data == "enter_squad_code" (в handle_text):
# После save_users(users), save_squads(squads):
#
#   new_achs = check_achievements(users[uid])
#   save_users(users)


# ── 10. ПРОВЕРКА ПРИ УРОНЕ БОССУ (apply_boss_damage) ──────────
# В конце apply_boss_damage(), ПЕРЕД return msg:
#
# ДОБАВЬ:
#   extra = {"boss_hit": True}
#   if boss["hp"] <= 0:
#       extra["boss_killed"] = True
#   new_achs = check_achievements(user, extra_ctx=extra)
#   # Добавь в msg если есть новые:
#   msg += format_new_achievements(new_achs)
#
# ВАЖНО: save_users(users) вызывается уже снаружи — дополнительно не нужен.


# ================================================================
# ПРИМЕР: как выглядит блок done_ после патча
# ================================================================

EXAMPLE_DONE_BLOCK = '''
    if data.startswith("done_"):
        task_id = data.replace("done_", "")
        today = str(date.today())
        task = next((t for t in user.get("tasks", []) if t["id"] == task_id), None)
        if not task:
            await query.answer("Задание не найдено", show_alert=True)
            return
        if task.get("done_date") == today:
            await query.answer("Уже выполнено сегодня ✅", show_alert=True)
            return
        task["done"] = True
        task["done_date"] = today
        user["attrs"][task["attr"]] = user["attrs"].get(task["attr"], 0) + task["attr_gain"]
        update_streak(user)
        leveled = add_xp(user, task["xp_gain"])
        user["reward_points"] = user.get("reward_points", 0) + 5
        boss_msg = await apply_boss_damage(uid, task["attr"], user, users, query)
        new_achs = check_achievements(user)          # ← ДОБАВЛЕНО
        save_users(users)
        attr = ATTRS[task["attr"]]
        msg = (
            f"✅ *{task[\'name\']}*\\n\\n"
            f"{attr[\'emoji\']} {attr[\'name\']} +{task[\'attr_gain\']} · ⭐ +{task[\'xp_gain\']} опыта · 🏆 +5\\n"
            f"🔥 Стрик: {user[\'streak\']} дн."
            f"{boss_msg}"
        )
        if leveled:
            gear = GEAR_UNLOCKS.get(user["level"], "")
            msg += f"\\n\\n🎉 *Уровень {user[\'level\']}!*"
            if gear:
                msg += f"\\nПолучено: {gear}"
        msg += format_new_achievements(new_achs)     # ← ДОБАВЛЕНО
        kb = [[InlineKeyboardButton("◀️ К заданиям", callback_data="tasks")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return
'''
