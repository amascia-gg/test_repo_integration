import asyncio
import os
import threading
from asyncio import create_subprocess_exec
from os import execl as osexecl
from sys import executable

import pyrogram
from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from aiofiles.os import remove as aioremove
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.errors import (
    FloodWait,
    InputUserDeactivated,
    PeerIdInvalid,
    UserIsBlocked,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from helpers import (
    add_user,
    create_telebin_page,
    delete_user,
    get_all_users,
    is_user_exist,
    pretify_search,
)
from search_helper import get_prod_link, poorvika_search

# config
bot_token = os.environ.get("TOKEN")
api_hash = os.environ.get("HASH")
api_id = os.environ.get("ID")
u_name = os.environ.get("BOT_USERNAME", "PoorvikaSearchBot")
db_url = os.environ.get("DATABASE_URL")
admin_list = os.environ.get(
    "ADMINS_ID",
    [1458096575],
)

# bot


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token
        )

    async def start(self):
        await super().start()
        print("<<[Bot Started]>>")
        try:
            if await aiopath.isfile(".restartmsg"):
                with open(".restartmsg") as f:
                    chat_id, msg_id = map(int, f)
                try:
                    await self.edit_message_text(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text="Restarted Successfully!",
                    )
                except BaseException:
                    pass
                await aioremove(".restartmsg")
        except Exception:
            pass

    async def stop(self, *args):
        await super().stop()
        print("<<[Bot Stopped]>>")


app = Bot()

# db setup
client = MongoClient(db_url)
db = client["mydb"]
collection = db["users"]


# start msg


@app.on_message(filters.command(["start"], prefixes=["/", "!", "."]))
async def send_start(
    client: pyrogram.client.Client,
    message: pyrogram.types.messages_and_media.message.Message,
):
    exist = is_user_exist(collection, message.from_user.id)
    if not exist:
        add_user(collection, message.from_user.id)
    if message.text.startswith("/start search_"):
        search_prod = threading.Thread(
            target=lambda: asyncio.run(get_prod_link(message, app))
        )
        search_prod.start()
        return
    await app.send_message(
        message.chat.id,
        f"__👋 Hi **{message.from_user.mention}**, i am Poorvika Search Bot. \n\nJust Send me ```/search Product_Name``` \nExample: `/search Samsung`__",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "👨‍💻 Owner", url="https://telegram.me/AnshumanPM_2006"
                    )
                ]
            ]
        ),
        reply_to_message_id=message.id,
    )


# Search Thread


def searchthread(message):
    try:
        query = str(message.text.split("/search ")[1])
    except BaseException:
        try:
            query = str(message.text.split(f"/search@{u_name} ")[1])
        except BaseException:
            app.send_message(
                message.chat.id,
                "Send any product link",
                reply_to_message_id=message.id,
            )
            return
    msg = app.send_message(
        message.chat.id, "⚡ __searching...__", reply_to_message_id=message.id
    )
    try:
        raw, name = poorvika_search(query)
        raw_html = pretify_search(raw, name)
        tf_page = create_telebin_page(raw_html)
        app.edit_message_text(
            message.chat.id,
            msg.id,
            f"**Searched Link:** __{tf_page}__\n\n**CC:** @AnshBotZone",
            disable_web_page_preview=True,
        )
        return
    except Exception as e:
        app.edit_message_text(
            message.chat.id,
            msg.id,
            f"**Error:** __{e}__ \n\n**CC:** @AnshBotZone",
            disable_web_page_preview=True,
        )
        return


# search msg
@app.on_message(filters.command(["search"], prefixes=["/", "!", "."]))
def search(
    client: pyrogram.client.Client,
    message: pyrogram.types.messages_and_media.message.Message,
):
    search = threading.Thread(target=lambda: searchthread(message), daemon=True)
    search.start()


# Send Broadcast Message


async def send_broadcast(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return 200
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return send_broadcast(user_id, message)
    except InputUserDeactivated:
        return 400
    except UserIsBlocked:
        return 400
    except PeerIdInvalid:
        return 400
    except Exception:
        return 500


# broadcast command
@app.on_message(
    filters.command(["broadcast"], prefixes=["/", "!", "."]) & filters.chat(admin_list)
)
async def send_cast(
    client: pyrogram.client.Client,
    message: pyrogram.types.messages_and_media.message.Message,
):
    try:
        cast_msg = message.reply_to_message
        if cast_msg:
            await app.send_message(
                message.chat.id,
                "Broadcast Started",
                reply_to_message_id=message.id,
            )
        else:
            await app.send_message(
                message.chat.id,
                "Reply To a Message For Broadcast",
                reply_to_message_id=message.id,
            )
            return
    except BaseException:
        await app.send_message(
            message.chat.id,
            "Reply To a Message For Broadcast",
            reply_to_message_id=message.id,
        )
        return
    all_users = get_all_users(collection)
    failed = 0
    success = 0
    for user_id in all_users:
        sts = await send_broadcast(user_id, cast_msg)
        if sts == 200:
            success += 1
        else:
            failed += 1
        if sts == 400:
            delete_user(collection, user_id)
    await app.send_message(
        message.chat.id,
        f"Broadcast Completed Successfully\n\n**Total User:** {len(all_users)}\n**Success:** {success}\n**Failed:** {failed}",
        reply_to_message_id=message.id,
    )


# restart msg
@app.on_message(filters.command(["restart"], prefixes=["/", "!", "."]))
async def restart(
    client: pyrogram.client.Client,
    message: pyrogram.types.messages_and_media.message.Message,
):
    if message.from_user.id not in admin_list:
        return await message.reply_text("<b>Needs Bot Admin For This Command...</b>")
    restart_message = await app.send_message(
        message.chat.id,
        "Restarting...",
        reply_to_message_id=message.id,
    )
    proc = await create_subprocess_exec("python3", "update.py")
    await proc.wait()
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{restart_message.chat.id}\n{restart_message.id}\n")
    osexecl(executable, executable, "main.py")


# server loop
app.run()