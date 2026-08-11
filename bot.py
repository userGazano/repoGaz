from datetime import datetime, timezone
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)
from sqlalchemy import select, func

from config import get_settings
from db import SessionLocal
from models import (
    User,
    Product,
    Account,
    Order,
    Purchase,
    AuditLog,
)
from inventory import reserve_account, release_account


log = logging.getLogger(__name__)

settings = get_settings()
dp = Dispatcher()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_id_set


def menu() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🛒 Каталог",
                callback_data="catalog",
            )
        ],
        [
            InlineKeyboardButton(
                text="👤 Мой аккаунт",
                callback_data="profile",
            ),
            InlineKeyboardButton(
                text="📦 Мои покупки",
                callback_data="my_accounts",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🤝 Рефералка",
                callback_data="referrals",
            ),
            InlineKeyboardButton(
                text="🆘 Поддержка",
                callback_data="support",
            ),
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def get_or_create_user(
    tg_user,
    referral: str | None = None,
):
    async with SessionLocal() as s:
        user = (
            await s.execute(
                select(User).where(
                    User.telegram_id == tg_user.id
                )
            )
        ).scalar_one_or_none()

        if not user:
            ref_id = None

            if referral:
                ref = (
                    await s.execute(
                        select(User).where(
                            User.referral_code == referral
                        )
                    )
                ).scalar_one_or_none()

                if ref and ref.telegram_id != tg_user.id:
                    ref_id = ref.id

            user = User(
                telegram_id=tg_user.id,
                username=tg_user.username,
                referral_code=f"u{tg_user.id}",
                referred_by_id=ref_id,
            )

            s.add(user)
            await s.commit()

        else:
            user.username = tg_user.username
            await s.commit()

        return user


@dp.message(CommandStart())
async def start(message: Message):
    arg = None

    if message.text and " " in message.text:
        arg = message.text.split(maxsplit=1)[1]

    user = await get_or_create_user(
        message.from_user,
        arg,
    )

    if user.is_blocked:
        await message.answer(
            "⛔ Доступ к магазину ограничен."
        )
        return

    await message.answer(
        f"✨ <b>{settings.shop_name}</b>\n\n"
        "Выбери раздел:",
        reply_markup=menu(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "home")
async def home(c: CallbackQuery):
    await c.answer()

    await c.message.edit_text(
        f"✨ <b>{settings.shop_name}</b>\n\n"
        "Выбери раздел:",
        reply_markup=menu(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "catalog")
async def catalog(c: CallbackQuery):
    await c.answer()

    async with SessionLocal() as s:
        products = (
            await s.execute(
                select(Product)
                .where(Product.active.is_(True))
                .where(
                    select(func.count(Account.id))
                    .where(
                        Account.product_id == Product.id,
                        Account.status == "available",
                    )
                    .scalar_subquery()
                    > 0
                )
                .order_by(Product.id.desc())
            )
        ).scalars().all()

    if not products:
        text = (
            "🛒 <b>Каталог</b>\n\n"
            "Пока нет товаров в наличии."
        )

        rows = [
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="home",
                )
            ]
        ]

    else:
        rows = [
            [
                InlineKeyboardButton(
                    text=f"{p.title} · {p.price_stars} ⭐",
                    callback_data=f"product:{p.id}",
                )
            ]
            for p in products[:30]
        ]

        rows.append(
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="home",
                )
            ]
        )

        text = (
            "🛒 <b>Каталог</b>\n\n"
            "Выбери товар:"
        )

    await c.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=rows
        ),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("product:"))
async def product(c: CallbackQuery):
    await c.answer()

    try:
        pid = int(c.data.split(":")[1])
    except (ValueError, IndexError):
        return

    async with SessionLocal() as s:
        p = await s.get(Product, pid)

        count = await s.scalar(
            select(func.count(Account.id)).where(
                Account.product_id == pid,
                Account.status == "available",
            )
        )

    if not p or not p.active or not count:
        await c.answer(
            "Товар недоступен",
            show_alert=True,
        )
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"⭐ Купить за {p.price_stars}",
                    callback_data=f"buy:{p.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Каталог",
                    callback_data="catalog",
                )
            ],
        ]
    )

    await c.message.edit_text(
        f"🌍 <b>{p.title}</b>\n\n"
        f"Страна: {p.country}\n"
        f"В наличии: <b>{count}</b>\n"
        f"Цена: <b>{p.price_stars} ⭐</b>\n\n"
        f"{p.description or 'Без описания.'}",
        reply_markup=kb,
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery):
    await c.answer()

    try:
        pid = int(c.data.split(":")[1])
    except (ValueError, IndexError):
        return

    async with SessionLocal() as s:
        p = await s.get(Product, pid)

        if not p or not p.active:
            await c.answer(
                "Товар недоступен",
                show_alert=True,
            )
            return

        account = await reserve_account(s, pid)

        if not account:
            await c.answer(
                "Товар только что закончился",
                show_alert=True,
            )
            return

        user_id = (
            await s.execute(
                select(User.id).where(
                    User.telegram_id == c.from_user.id
                )
            )
        ).scalar_one()

        order = Order(
            user_id=user_id,
            product_id=pid,
            account_id=account.id,
            amount_stars=p.price_stars,
            status="pending",
        )

        s.add(order)
        await s.commit()

        order_id = order.id
        price = p.price_stars
        title = p.title
        description = (
            p.description or "Покупка товара"
        )[:255]

    try:
        await c.message.answer_invoice(
            title=title[:32],
            description=description,
            payload=f"order:{order_id}",
            currency="XTR",
            prices=[
                LabeledPrice(
                    label=title[:32],
                    amount=price,
                )
            ],
        )

    except Exception:
        log.exception(
            "Failed to create invoice for order %s",
            order_id,
        )

        async with SessionLocal() as s:
            await release_account(
                s,
                account.id,
            )

            order = await s.get(
                Order,
                order_id,
            )

            if order:
                order.status = "cancelled"

            await s.commit()

        raise


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    if not q.invoice_payload.startswith("order:"):
        await q.answer(
            ok=False,
            error_message="Некорректный заказ.",
        )
        return

    try:
        order_id = int(
            q.invoice_payload.split(":")[1]
        )
    except (ValueError, IndexError):
        await q.answer(
            ok=False,
            error_message="Некорректный заказ.",
        )
        return

    async with SessionLocal() as s:
        order = await s.get(
            Order,
            order_id,
        )

        ok = bool(
            order
            and order.status == "pending"
        )

    await q.answer(
        ok=ok,
        error_message=(
            None
            if ok
            else "Заказ уже недоступен."
        ),
    )


@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    payload = payment.invoice_payload

    if not payload.startswith("order:"):
        await message.answer(
            "Оплата получена, но заказ имеет "
            "некорректный формат. Обратитесь в поддержку."
        )
        return

    try:
        order_id = int(
            payload.split(":")[1]
        )
    except (ValueError, IndexError):
        await message.answer(
            "Некорректный номер заказа."
        )
        return

    async with SessionLocal() as s:
        order = await s.get(
            Order,
            order_id,
            with_for_update=True,
        )

        if not order:
            await message.answer(
                "Оплата получена, но заказ не найден. "
                "Обратитесь в поддержку."
            )
            return

        if order.status == "paid":
            purchase = (
                await s.execute(
                    select(Purchase).where(
                        Purchase.order_id == order.id
                    )
                )
            ).scalar_one_or_none()

            account = (
                await s.get(
                    Account,
                    purchase.account_id,
                )
                if purchase
                else None
            )

            if account and account.encrypted_payload:
                await message.answer(
                    "✅ Оплата уже обработана.\n\n"
                    "Ваши данные:\n"
                    f"<code>{account.encrypted_payload[:3500]}</code>",
                    parse_mode="HTML",
                )
            else:
                await message.answer(
                    "✅ Оплата уже обработана. "
                    "Заказ находится в обработке."
                )

            return

        if (
            order.status != "pending"
            or order.user_id != message.from_user.id
        ):
            await message.answer(
                "⚠️ Заказ недоступен или уже обработан."
            )
            return

        account = await s.get(
            Account,
            order.account_id,
            with_for_update=True,
        )

        if (
            not account
            or account.status != "reserved"
        ):
            order.status = "failed"
            await s.commit()

            await message.answer(
                "⚠️ Оплата прошла, но товар недоступен. "
                "Обратитесь в поддержку."
            )
            return

        order.status = "paid"

        order.telegram_charge_id = (
            payment.telegram_payment_charge_id
        )

        order.telegram_payment_id = getattr(
            payment,
            "provider_payment_charge_id",
            None,
        )

        order.paid_at = (
            datetime.now(timezone.utc)
            .replace(tzinfo=None)
        )

        account.status = "sold"
        account.sold_at = order.paid_at

        purchase = Purchase(
            order_id=order.id,
            user_id=order.user_id,
            account_id=account.id,
            delivered_at=order.paid_at,
        )

        s.add(purchase)

        s.add(
            AuditLog(
                actor_telegram_id=message.from_user.id,
                action="purchase_paid",
                target_type="order",
                target_id=str(order.id),
                details=f"account_id={account.id}",
            )
        )

        await s.commit()

        payload_data = account.encrypted_payload

    if payload_data:
        await message.answer(
            "✅ <b>Оплата подтверждена!</b>\n\n"
            "Ваш заказ:\n"
            f"<code>{payload_data[:3500]}</code>\n\n"
            "Сохраните данные. Если возникнет проблема — "
            "обратитесь в поддержку.",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "✅ Оплата подтверждена. "
            "Данные заказа пока не заполнены — "
            "обратитесь в поддержку."
        )


@dp.callback_query(F.data == "profile")
async def profile(c: CallbackQuery):
    await c.answer()

    async with SessionLocal() as s:
        user = (
            await s.execute(
                select(User).where(
                    User.telegram_id == c.from_user.id
                )
            )
        ).scalar_one_or_none()

        count = (
            await s.scalar(
                select(func.count(Purchase.id)).where(
                    Purchase.user_id == user.id
                )
            )
            if user
            else 0
        )

    await c.message.edit_text(
        f"👤 <b>Мой аккаунт</b>\n\n"
        f"ID: <code>{c.from_user.id}</code>\n"
        f"Покупок: <b>{count}</b>",
        reply_markup=menu(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "my_accounts")
async def my_accounts(c: CallbackQuery):
    await c.answer()

    async with SessionLocal() as s:
        user = (
            await s.execute(
                select(User).where(
                    User.telegram_id == c.from_user.id
                )
            )
        ).scalar_one_or_none()

        purchases = []

        if user:
            purchases = (
                await s.execute(
                    select(
                        Purchase,
                        Account,
                        Order,
                    )
                    .join(
                        Account,
                        Account.id == Purchase.account_id,
                    )
                    .join(
                        Order,
                        Order.id == Purchase.order_id,
                    )
                    .where(
                        Purchase.user_id == user.id
                    )
                    .order_by(Purchase.id.desc())
                    .limit(10)
                )
            ).all()

    if not purchases:
        text = (
            "📦 <b>Мои покупки</b>\n\n"
            "Покупок пока нет."
        )
    else:
        lines = ["📦 <b>Мои покупки</b>"]

        for purchase, account, order in purchases:
            lines.append(
                f"\nЗаказ #{order.id} · "
                f"{order.amount_stars} ⭐\n"
                f"<code>{(account.encrypted_payload or 'данные не заполнены')[:1200]}</code>"
            )

        text = "\n".join(lines)

    await c.message.edit_text(
        text,
        reply_markup=menu(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "referrals")
async def referrals(c: CallbackQuery):
    await c.answer()

    async with SessionLocal() as s:
        u = (
            await s.execute(
                select(User).where(
                    User.telegram_id == c.from_user.id
                )
            )
        ).scalar_one_or_none()

    code = (
        u.referral_code
        if u
        else f"u{c.from_user.id}"
    )

    me = await c.bot.get_me()

    await c.message.edit_text(
        f"🤝 <b>Реферальная программа</b>\n\n"
        f"Твой код: <code>{code}</code>\n"
        f"Ссылка: "
        f"<code>https://t.me/{me.username}?start={code}</code>",
        reply_markup=menu(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "support")
async def support(c: CallbackQuery):
    await c.answer()

    target = (
        f"@{settings.support_username}"
        if settings.support_username
        else "администратору"
    )

    await c.message.edit_text(
        f"🆘 <b>Поддержка</b>\n\n"
        f"Напишите {target}.",
        reply_markup=menu(),
        parse_mode="HTML",
    )


# =========================
# ADMIN
# =========================


@dp.message(Command("admin"))
async def admin(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with SessionLocal() as s:
        users = await s.scalar(
            select(func.count(User.id))
        )

        products = await s.scalar(
            select(func.count(Product.id))
        )

        available = await s.scalar(
            select(func.count(Account.id)).where(
                Account.status == "available"
            )
        )

        reserved = await s.scalar(
            select(func.count(Account.id)).where(
                Account.status == "reserved"
            )
        )

        sold = await s.scalar(
            select(func.count(Account.id)).where(
                Account.status == "sold"
            )
        )

        revenue = await s.scalar(
            select(
                func.coalesce(
                    func.sum(Order.amount_stars),
                    0,
                )
            ).where(
                Order.status == "paid"
            )
        )

    await message.answer(
        "🛠 <b>Админка</b>\n\n"
        f"Пользователи: {users}\n"
        f"Товары: {products}\n"
        f"Аккаунты: 🟢 {available} · "
        f"🟡 {reserved} · 🔴 {sold}\n"
        f"Выручка: ⭐ {revenue}\n\n"
        "<b>Команды</b>\n"
        "/products — товары\n"
        "/accounts — аккаунты\n"
        "/add_product название|страна|цена|описание\n"
        "/add_account product_id|страна|метка|данные\n"
        "/set_account account_id|available|unavailable\n"
        "/set_product product_id|on/off",
        parse_mode="HTML",
    )


@dp.message(Command("products"))
async def admin_products(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(Product)
                .order_by(Product.id.desc())
                .limit(30)
            )
        ).scalars().all()

        out = ["🛍 <b>Товары</b>"]

        for p in rows:
            count = await s.scalar(
                select(func.count(Account.id)).where(
                    Account.product_id == p.id,
                    Account.status == "available",
                )
            )

            out.append(
                f"#{p.id} "
                f"{'🟢' if p.active else '⚫'} "
                f"{p.title} · "
                f"{p.price_stars}⭐ · "
                f"в наличии {count}"
            )

    await message.answer(
        "\n".join(out),
        parse_mode="HTML",
    )


@dp.message(Command("accounts"))
async def admin_accounts(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(Account)
                .order_by(Account.id.desc())
                .limit(50)
            )
        ).scalars().all()

    if not rows:
        await message.answer(
            "Аккаунтов нет."
        )
        return

    text = ["📦 <b>Последние аккаунты</b>"]

    for a in rows:
        text.append(
            f"#{a.id} "
            f"product={a.product_id} · "
            f"{a.status} · "
            f"{a.country} · "
            f"{a.public_label}"
        )

    await message.answer(
        "\n".join(text),
        parse_mode="HTML",
    )


@dp.message(Command("add_product"))
async def add_product(message: Message):
    if not is_admin(message.from_user.id):
        return

    raw = message.text.partition(" ")[2]

    parts = [
        x.strip()
        for x in raw.split("|", 3)
    ]

    if len(parts) != 4:
        await message.answer(
            "Формат: "
            "/add_product название|страна|цена|описание"
        )
        return

    title, country, price, description = parts

    try:
        price = int(price)

        if price <= 0:
            raise ValueError

    except ValueError:
        await message.answer(
            "Цена должна быть положительным целым числом."
        )
        return

    async with SessionLocal() as s:
        p = Product(
            title=title[:255],
            country=country[:100],
            price_stars=price,
            description=description,
        )

        s.add(p)

        await s.commit()

        await message.answer(
            f"✅ Товар создан: #{p.id}"
        )


@dp.message(Command("add_account"))
async def add_account(message: Message):
    if not is_admin(message.from_user.id):
        return

    raw = message.text.partition(" ")[2]

    parts = [
        x.strip()
        for x in raw.split("|", 3)
    ]

    if len(parts) != 4:
        await message.answer(
            "Формат: "
            "/add_account product_id|страна|метка|данные"
        )
        return

    try:
        product_id = int(parts[0])

    except ValueError:
        await message.answer(
            "product_id должен быть числом."
        )
        return

    async with SessionLocal() as s:
        p = await s.get(
            Product,
            product_id,
        )

        if not p:
            await message.answer(
                "Товар не найден."
            )
            return

        a = Account(
            product_id=product_id,
            country=parts[1][:100],
            public_label=parts[2][:255],
            encrypted_payload=parts[3],
            status="available",
        )

        s.add(a)

        s.add(
            AuditLog(
                actor_telegram_id=message.from_user.id,
                action="account_added",
                target_type="account",
                target_id="new",
                details=f"product_id={product_id}",
            )
        )

        await s.commit()

        await message.answer(
            f"✅ Аккаунт добавлен: #{a.id}"
        )


@dp.message(Command("set_account"))
async def set_account(message: Message):
    if not is_admin(message.from_user.id):
        return

    raw = message.text.partition(" ")[2]

    parts = [
        x.strip()
        for x in raw.split("|", 1)
    ]

    if (
        len(parts) != 2
        or parts[1] not in {
            "available",
            "unavailable",
        }
    ):
        await message.answer(
            "Формат: "
            "/set_account account_id|available "
            "или unavailable"
        )
        return

    try:
        aid = int(parts[0])

    except ValueError:
        await message.answer(
            "ID должен быть числом."
        )
        return

    async with SessionLocal() as s:
        a = await s.get(
            Account,
            aid,
            with_for_update=True,
        )

        if not a:
            await message.answer(
                "Аккаунт не найден."
            )
            return

        if a.status == "sold":
            await message.answer(
                "Проданный аккаунт нельзя вернуть в продажу."
            )
            return

        a.status = parts[1]
        a.reserved_at = None

        s.add(
            AuditLog(
                actor_telegram_id=message.from_user.id,
                action="account_status_changed",
                target_type="account",
                target_id=str(aid),
                details=parts[1],
            )
        )

        await s.commit()

    await message.answer(
        f"✅ Аккаунт #{aid}: {parts[1]}"
    )


@dp.message(Command("set_product"))
async def set_product(message: Message):
    if not is_admin(message.from_user.id):
        return

    raw = message.text.partition(" ")[2]

    parts = [
        x.strip()
        for x in raw.split("|", 1)
    ]

    if (
        len(parts) != 2
        or parts[1] not in {"on", "off"}
    ):
        await message.answer(
            "Формат: "
            "/set_product product_id|on или off"
        )
        return

    try:
        pid = int(parts[0])

    except ValueError:
        await message.answer(
            "ID должен быть числом."
        )
        return

    async with SessionLocal() as s:
        p = await s.get(
            Product,
            pid,
        )

        if not p:
            await message.answer(
                "Товар не найден."
            )
            return

        p.active = parts[1] == "on"

        await s.commit()

    await message.answer(
        f"✅ Товар #{pid}: "
        f"{'включён' if p.active else 'выключен'}"
    )


async def run_bot():
    log.info("=" * 60)
    log.info("🤖 TELEGRAM BOT STARTING")
    log.info("=" * 60)

    token = settings.bot_token

    if not token:
        log.error("❌ BOT_TOKEN is empty!")
        raise RuntimeError(
            "BOT_TOKEN environment variable is not set"
        )

    log.info(
        "🔑 BOT_TOKEN loaded successfully (length=%d)",
        len(token),
    )

    bot = Bot(token)

    try:
        log.info("📡 Connecting to Telegram...")

        me = await bot.get_me()

        log.info("=" * 60)
        log.info("✅ TELEGRAM CONNECTION SUCCESSFUL")
        log.info("🤖 Bot ID: %s", me.id)
        log.info("👤 Bot username: @%s", me.username)
        log.info("📛 Bot name: %s", me.first_name)
        log.info("=" * 60)

        log.info("📥 Starting polling...")

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )

    except Exception:
        log.exception("💥 TELEGRAM BOT CRASHED")
        raise

    finally:
        log.info("🛑 Closing Telegram bot session...")
        await bot.session.close()
        log.info("👋 Telegram bot stopped")
