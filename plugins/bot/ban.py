import asyncio
import logging
from contextlib import suppress
from string import ascii_lowercase
from typing import Dict, Union
from pyrogram import Client, filters
from pyrogram.enums import ChatMembersFilter, ChatMemberStatus, ChatType
from pyrogram.types import (
    CallbackQuery,
    ChatPermissions,
    ChatPrivileges,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from pyrogram.errors import FloodWait, ChatAdminRequired, UserNotParticipant, InviteHashExpired, PeerIdInvalid
from AloneX import app
from AloneX.misc import SUDOERS, SPECIAL_ID
from AloneX.core.mongo import mongodb
from utils.error import capture_err
from AloneX.utils.keyboard import ikb
from AloneX.utils.database import save_filter
from AloneX.utils.functions import (
    extract_user_and_reason,
    time_converter,
)
from utils.permissions import adminsOnly, member_permissions
from config import BANNED_USERS

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

warnsdb = mongodb.warns

__MODULE__ = "Bᴀɴ"
__HELP__ = """
/ban - Ban A User
/banall - Ban All Users
/sban - Delete all messages of user that sended in group and ban the user
/tban - Ban A User For Specific Time
/unban - Unban A User
/warn - Warn A User
/swarn - Delete all the message sended in group and warn the user
/rmwarns - Remove All Warning of A User
/warns - Show Warning Of A User
/kick - Kick A User
/skick - Delete the replied message kicking its sender
/purge - Purge Messages
/purge [n] - Purge "n" number of messages from replied message
/del - Delete Replied Message
/promote - Promote A Member
/fullpromote - Promote A Member With All Rights
/demote - Demote A Member
/pin - Pin A Message
/unpin - unpin a message
/unpinall - unpinall messages
/mute - Mute A User
/tmute - Mute A User For Specific Time
/unmute - Unmute A User
/zombies - Ban Deleted Accounts
/report | @admins | @admin - Report A Message To Admins."""

async def int_to_alpha(user_id: int) -> str:
    alphabet = list(ascii_lowercase)[:10]
    text = ""
    user_id = str(user_id)
    for i in user_id:
        text += alphabet[int(i)]
    return text

async def extract_user(message: Message) -> Union[int, str, None]:
    """Extract user ID or username from a message."""
    user_id = None

    # Check if the message is a reply to another message
    if message.reply_to_message:
        return message.reply_to_message.from_user.id

    # Check if the message contains text
    if not message.text:
        return None

    # Check if the message contains entities (e.g., mentions, user IDs)
    if message.entities:
        try:
            # If the message starts with a command (e.g., "/unban"), skip the first entity (the command itself)
            if message.text.startswith("/"):
                if len(message.entities) > 1:
                    msg_entities = message.entities[1]
                else:
                    return None
            else:
                msg_entities = message.entities[0]

            # Check if the entity is a mention or text mention
            if msg_entities.type in ["mention", "text_mention"]:
                if msg_entities.type == "mention":
                    # Extract username from the mention (e.g., "@username")
                    username = message.text[msg_entities.offset : msg_entities.offset + msg_entities.length]
                    user = await app.get_users(username)
                    return user.id
                elif msg_entities.type == "text_mention":
                    # Extract user ID from the text mention
                    return msg_entities.user.id

        except (IndexError, AttributeError, KeyError) as e:
            logger.error(f"Error extracting user: {e}")
            return None

    # If no entities are found, try to extract the username from the command arguments
    if len(message.command) > 1:
        user_arg = message.command[1]
        if user_arg.startswith("@"):
            try:
                user = await app.get_users(user_arg)
                return user.id
            except Exception as e:
                logger.error(f"Error extracting user from command argument: {e}")
                return None
    return None

async def get_warns_count() -> dict:
    chats_count = 0
    warns_count = 0
    async for chat in warnsdb.find({"chat_id": {"$lt": 0}}):
        for user in chat["warns"]:
            warns_count += chat["warns"][user]["warns"]
        chats_count += 1
    return {"chats_count": chats_count, "warns_count": warns_count}

async def get_warns(chat_id: int) -> Dict[str, int]:
    warns = await warnsdb.find_one({"chat_id": chat_id})
    return warns["warns"] if warns else {}

async def get_warn(chat_id: int, name: str) -> Union[bool, dict]:
    name = name.lower().strip()
    warns = await get_warns(chat_id)
    return warns.get(name)

async def add_warn(chat_id: int, name: str, warn: dict):
    name = name.lower().strip()
    warns = await get_warns(chat_id)
    warns[name] = warn
    await warnsdb.update_one({"chat_id": chat_id}, {"$set": {"warns": warns}}, upsert=True)

async def remove_warns(chat_id: int, name: str) -> bool:
    warnsd = await get_warns(chat_id)
    name = name.lower().strip()
    if name in warnsd:
        del warnsd[name]
        await warnsdb.update_one({"chat_id": chat_id}, {"$set": {"warns": warnsd}}, upsert=True)
        return True
    return False

@app.on_message(filters.command(["kick", "skick"]) & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def kickFunc(_, message: Message):
    user_id, reason = await extract_user_and_reason(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ")
    if user_id == app.id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴋɪᴄᴋ ᴍʏsᴇʟғ, ɪ ᴄᴀɴ ʟᴇᴀᴠᴇ ɪғ ʏᴏᴜ ᴡᴀɴᴛ.")
    if user_id in SUDOERS:
        return await message.reply_text("ʏᴏᴜ ᴡᴀɴɴᴀ ᴋɪᴄᴋ ᴛʜᴇ ᴇʟᴇᴠᴀᴛᴇᴅ ᴏɴᴇ ?")
    if user_id in [member.user.id async for member in app.get_chat_members(chat_id=message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS)]:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴋɪᴄᴋ ᴀɴ ᴀᴅᴍɪɴ, ʏᴏᴜ ᴋɴᴏᴡ ᴛʜᴇ ʀᴜʟᴇs, ʏᴏᴜ ᴋɴᴏᴡ ᴛʜᴇ ʀᴜʟᴇs, sᴏ ᴅᴏ ɪ ")
    mention = (await app.get_users(user_id)).mention
    msg = f"""
**ᴋɪᴄᴋᴇᴅ ᴜsᴇʀ:** {mention}
**ᴋɪᴄᴋᴇᴅ ʙʏ:** {message.from_user.mention if message.from_user else 'ᴀɴᴏɴᴍᴏᴜs'}
**ʀᴇᴀsᴏɴ:** {reason or 'ɴᴏ ʀᴇᴀsᴏɴ ᴘʀᴏᴠɪᴅᴇᴅ'}"""
    await message.chat.ban_member(user_id)
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(msg)
    await asyncio.sleep(1)
    await message.chat.unban_member(user_id)
    if message.command[0][0] == "s":
        await message.reply_to_message.delete()
        await app.delete_user_history(message.chat.id, user_id)

@app.on_message(filters.command(["ban", "sban", "tban"]) & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def banFunc(_, message: Message):
    user_id, reason = await extract_user_and_reason(message, sender_chat=True)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")
    if user_id == app.id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ʙᴀɴ ᴍʏsᴇʟғ, ɪ ᴄᴀɴ ʟᴇᴀᴠᴇ ɪғ ʏᴏᴜ ᴡᴀɴᴛ.")
    if user_id in SUDOERS:
        return await message.reply_text("ʏᴏᴜ ᴡᴀɴɴᴀ ʙᴀɴ ᴛʜᴇ ᴇʟᴇᴠᴀᴛᴇᴅ ᴏɴᴇ?, ʀᴇᴄᴏɴsɪᴅᴇʀ!")
    if user_id in [member.user.id async for member in app.get_chat_members(chat_id=message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS)]:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ʙᴀɴ ᴀɴ ᴀᴅᴍɪɴ, ʏᴏᴜ ᴋɴᴏᴡ ᴛʜᴇ ʀᴜʟᴇs, sᴏ ᴅᴏ ɪ.")
    try:
        mention = (await app.get_users(user_id)).mention
    except IndexError:
        mention = message.reply_to_message.sender_chat.title if message.reply_to_message else "Anon"
    msg = f"**ʙᴀɴɴᴇᴅ ᴜsᴇʀ:** {mention}\n**ʙᴀɴɴᴇᴅ ʙʏ:** {message.from_user.mention if message.from_user else 'Anon'}\n"
    if message.command[0][0] == "s":
        await message.reply_to_message.delete()
        await app.delete_user_history(message.chat.id, user_id)
    if message.command[0] == "tban":
        split = reason.split(None, 1)
        time_value = split[0]
        temp_reason = split[1] if len(split) > 1 else ""
        temp_ban = await time_converter(message, time_value)
        msg += f"**ʙᴀɴɴᴇᴅ ғᴏʀ:** {time_value}\n"
        if temp_reason:
            msg += f"**ʀᴇᴀsᴏɴ:** {temp_reason}"
        with suppress(AttributeError):
            if len(time_value[:-1]) < 3:
                await message.chat.ban_member(user_id, until_date=temp_ban)
                replied_message = message.reply_to_message
                if replied_message:
                    message = replied_message
                await message.reply_text(msg)
            else:
                await message.reply_text("ʏᴏᴜ ᴄᴀɴ'ᴛ ᴜsᴇ ᴍᴏʀᴇ ᴛʜᴀɴ 𝟿𝟿")
        return
    if reason:
        msg += f"**ʀᴇᴀsᴏɴ:** {reason}"
    await message.chat.ban_member(user_id)
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(msg)

@app.on_message(filters.command("unban") & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def unban_func(_, message: Message):
    # Extract user ID from the message text if it's provided directly
    if len(message.command) > 1:
        user_id = message.command[1]
    else:
        # Fall back to the extract_user function
        user_id = await extract_user(message)
    
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ. ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴜsᴇʀɴᴀᴍᴇ/ɪᴅ.")

    try:
        user_id = int(user_id)  # Ensure user_id is an integer
    except (ValueError, TypeError):
        return await message.reply_text("ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ.")

    reply = message.reply_to_message
    if reply and reply.sender_chat and reply.sender_chat != message.chat.id:
        return await message.reply_text("ʏᴏᴜ ᴄᴀɴɴᴏᴛ ᴜɴʙᴀɴ ᴀ ᴄʜᴀɴɴᴇʟ.")

    logger.info(f"Unbanning User ID: {user_id}, Type: {type(user_id)}")
    await message.chat.unban_member(user_id)
    umention = (await app.get_users(user_id)).mention
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(f"ᴜɴʙᴀɴɴᴇᴅ! {umention}")

# Database to store custom titles (example using a dictionary; replace with a real database)
custom_titles_db = {}

@app.on_message(filters.command(["promote", "fullpromote"]) & ~filters.private)
@adminsOnly("can_promote_members")
async def promoteFunc(client: Client, message: Message):
    try:
        # Extract user ID and admin title from the command
        if len(message.command) > 1:
            user = message.command[1]
            admin_title = " ".join(message.command[2:]) if len(message.command) > 2 else "Admin"
        else:
            # Fall back to extracting user from replied message
            user = await extract_user(message)
            admin_title = "Admin"

        if not user:
            return await message.reply_text("User not found.")

        try:
            user_id = int(user)  # Try to convert to integer (in case of user ID)
        except ValueError:
            # If it's not a user ID, assume it's a username and extract the user
            try:
                user_obj = await client.get_users(user)
                user_id = user_obj.id
            except Exception as e:
                logger.error(f"Error extracting user: {e}")
                return await message.reply_text("User not found.")

        # Ensure the bot has the necessary permissions
        bot = (await client.get_chat_member(message.chat.id, client.me.id)).privileges
        if not bot or not bot.can_promote_members:
            return await message.reply_text("I don't have enough permissions to promote members.")

        # Check if the user is the bot itself
        if user_id == client.me.id:
            return await message.reply_text("I can't promote myself.")

        # Check if the user is a member of the group
        try:
            member = await client.get_chat_member(message.chat.id, user_id)
            if member.status == "left" or member.status == "kicked":
                return await message.reply_text(f"User {user_obj.mention} is not in this group. They must join first to be promoted.")
        except UserNotParticipant:
            return await message.reply_text(f"User {user_obj.mention} is not in this group. They must join first to be promoted.")

        # Promote the user
        try:
            if message.command[0][0] == "f":  # Full promote
                await client.promote_chat_member(
                    chat_id=message.chat.id,
                    user_id=user_id,
                    privileges=ChatPrivileges(
                        can_change_info=True,
                        can_delete_messages=True,
                        can_invite_users=True,
                        can_restrict_members=True,
                        can_pin_messages=True,
                        can_promote_members=True,
                        can_manage_chat=True,
                        can_manage_video_chats=True,
                    )
                )
            else:  # Normal promote
                await client.promote_chat_member(
                    chat_id=message.chat.id,
                    user_id=user_id,
                    privileges=ChatPrivileges(
                        can_change_info=False,
                        can_delete_messages=True,
                        can_invite_users=True,
                        can_restrict_members=False,
                        can_pin_messages=False,
                        can_promote_members=False,
                        can_manage_chat=True,
                        can_manage_video_chats=True,
                    )
                )

            # Store the custom title in the database (even for basic groups)
            custom_titles_db[(message.chat.id, user_id)] = admin_title

            # Check if the chat is a supergroup
            chat = await client.get_chat(message.chat.id)
            is_supergroup = chat.type == ChatType.SUPERGROUP

            # Set the admin title only if the chat is a supergroup
            if is_supergroup:
                try:
                    await client.set_administrator_title(
                        chat_id=message.chat.id,
                        user_id=user_id,
                        title=admin_title
                    )
                except Exception as e:
                    logger.error(f"Error setting admin title: {e}")
                    await message.reply_text(f"Failed to set admin title: {e}")

            # Notify the chat about the promotion
            user_mention = (await client.get_users(user_id)).mention
            if is_supergroup:
                await message.reply_text(f"Promoted! {user_mention} with title: {admin_title}")
            else:
                await message.reply_text(f"Promoted! {user_mention} with title: {admin_title} (Note: Custom titles are not officially supported in this chat type).")

        except PeerIdInvalid:
            await message.reply_text("The user is not in this group. They must join first to be promoted.")
        except Exception as e:
            logger.error(f"Error promoting user: {e}")
            await message.reply_text(f"Failed to promote user: {e}")

    except Exception as e:
        logger.error(f"Unexpected error in promoteFunc: {e}")
        await message.reply_text(f"An unexpected error occurred: {e}")

@app.on_message(filters.command("purge") & ~filters.private)
@adminsOnly("can_delete_messages")
async def purgeFunc(_, message: Message):
    repliedmsg = message.reply_to_message
    await message.delete()
    if not repliedmsg:
        return await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴘᴜʀɢᴇ ғʀᴏᴍ.")
    cmd = message.command
    if len(cmd) > 1 and cmd[1].isdigit():
        purge_to = repliedmsg.id + int(cmd[1])
        if purge_to > message.id:
            purge_to = message.id
    else:
        purge_to = message.id
    chat_id = message.chat.id
    message_ids = []
    for message_id in range(repliedmsg.id, purge_to):
        message_ids.append(message_id)
        if len(message_ids) == 100:
            await app.delete_messages(chat_id=chat_id, message_ids=message_ids, revoke=True)
            message_ids = []
    if len(message_ids) > 0:
        await app.delete_messages(chat_id=chat_id, message_ids=message_ids, revoke=True)

@app.on_message(filters.command("del") & ~filters.private)
@adminsOnly("can_delete_messages")
async def deleteFunc(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴅᴇʟᴇᴛᴇ ɪᴛ")
    await message.reply_to_message.delete()
    await message.delete()

@app.on_message(filters.command("demote") & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_promote_members")
async def demote(_, message: Message):
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")
    if user_id == app.id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴅᴇᴍᴏᴛᴇ ᴍʏsᴇʟғ.")
    if user_id in SUDOERS:
        return await message.reply_text("ʏᴏᴜ ᴡᴀɴɴᴀ ᴅᴇᴍᴏᴛᴇ ᴛʜᴇ ᴇʟᴇᴠᴀᴛᴇᴅ ᴏɴᴇ?, ʀᴇᴄᴏɴsɪᴅᴇʀ!")
    try:
        member = await app.get_chat_member(message.chat.id, user_id)
        if member.status == ChatMemberStatus.ADMINISTRATOR:
            await message.chat.promote_member(
                user_id=user_id,
                privileges=ChatPrivileges(
                    can_change_info=False,
                    can_invite_users=False,
                    can_delete_messages=False,
                    can_restrict_members=False,
                    can_pin_messages=False,
                    can_promote_members=False,
                    can_manage_chat=False,
                    can_manage_video_chats=False,
                ),
            )
            umention = (await app.get_users(user_id)).mention
            await message.reply_text(f"ᴅᴇᴍᴏᴛᴇᴅ! {umention}")
        else:
            await message.reply_text("ᴛʜᴇ ᴘᴇʀsᴏɴ ʏᴏᴜ ᴍᴇɴᴛɪᴏɴᴇᴅ ɪs ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ.")
    except Exception as e:
        await message.reply_text(e)

@app.on_message(filters.command(["unpinall"]) & filters.group & ~BANNED_USERS)
@adminsOnly("can_pin_messages")
async def pin(_, message: Message):
    if message.command[0] == "unpinall":
        return await message.reply_text(
            "Aʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴜɴᴘɪɴ ᴀʟʟ ᴍᴇssᴀɢᴇs?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(text="ʏᴇs", callback_data="unpin_yes"),
                     InlineKeyboardButton(text="ɴᴏ", callback_data="unpin_no")],
                ]
            ),
        )

@app.on_callback_query(filters.regex(r"unpin_(yes|no)"))
async def callback_query_handler(_, query: CallbackQuery):
    if query.data == "unpin_yes":
        await app.unpin_all_chat_messages(query.message.chat.id)
        return await query.message.edit_text("Aʟʟ ᴘɪɴɴᴇᴅ ᴍᴇssᴀɢᴇs ʜᴀᴠᴇ ʙᴇᴇɴ ᴜɴᴘɪɴɴᴇᴅ.")
    elif query.data == "unpin_no":
        return await query.message.edit_text("Uɴᴘɪɴ ᴏғ ᴀʟʟ ᴘɪɴɴᴇᴅ ᴍᴇssᴀɢᴇs ʜᴀs ʙᴇᴇɴ ᴄᴀɴᴄᴇʟʟᴇᴅ.")

@app.on_message(filters.command(["pin", "unpin"]) & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_pin_messages")
async def pin(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴘɪɴ/ᴜɴᴘɪɴ ɪᴛ.")
    r = message.reply_to_message
    if message.command[0][0] == "u":
        await r.unpin()
        return await message.reply_text(f"ᴜɴᴘɪɴɴᴇᴅ [ᴛʜɪs]({r.link}) ᴍᴇssᴀɢᴇ.", disable_web_page_preview=True)
    await r.pin(disable_notification=True)
    await message.reply(f"ᴘɪɴɴᴇᴅ [ᴛʜɪs]({r.link}) ᴍᴇssᴀɢᴇ.", disable_web_page_preview=True)
    msg = "ᴘʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ᴛʜᴇ ᴘɪɴɴᴇᴅ ᴍᴇssᴀɢᴇ: ~ " + f"[Check, {r.link}]"
    filter_ = dict(type="text", data=msg)
    await save_filter(message.chat.id, "~pinned", filter_)

@app.on_message(filters.command(["mute", "tmute"]) & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def mute(_, message: Message):
    user_id, reason = await extract_user_and_reason(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")
    if user_id == app.id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴍᴜᴛᴇ ᴍʏsᴇʟғ.")
    if user_id in SUDOERS:
        return await message.reply_text("ʏᴏᴜ ᴡᴀɴɴᴀ ᴍᴜᴛᴇ ᴛʜᴇ ᴇʟᴇᴠᴀᴛᴇᴅ ᴏɴᴇ?, ʀᴇᴄᴏɴsɪᴅᴇʀ!")
    if user_id in [member.user.id async for member in app.get_chat_members(chat_id=message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS)]:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴍᴜᴛᴇ ᴀɴ ᴀᴅᴍɪɴ, ʏᴏᴜ ᴋɴᴏᴡ ᴛʜᴇ ʀᴜʟᴇs, sᴏ ᴅᴏ ɪ.")
    mention = (await app.get_users(user_id)).mention
    keyboard = ikb({"🚨  Unmute  🚨": f"unmute_{user_id}"})
    msg = f"**ᴍᴜᴛᴇᴅ ᴜsᴇʀ:** {mention}\n**ᴍᴜᴛᴇᴅ ʙʏ:** {message.from_user.mention if message.from_user else 'Anon'}\n"
    if message.command[0] == "tmute":
        split = reason.split(None, 1)
        time_value = split[0]
        temp_reason = split[1] if len(split) > 1 else ""
        temp_mute = await time_converter(message, time_value)
        msg += f"**ᴍᴜᴛᴇᴅ ғᴏʀ:** {time_value}\n"
        if temp_reason:
            msg += f"**ʀᴇᴀsᴏɴ:** {temp_reason}"
        try:
            if len(time_value[:-1]) < 3:
                await message.chat.restrict_member(user_id, permissions=ChatPermissions(), until_date=temp_mute)
                replied_message = message.reply_to_message
                if replied_message:
                    message = replied_message
                await message.reply_text(msg, reply_markup=keyboard)
            else:
                await message.reply_text("ʏᴏᴜ ᴄᴀɴ'ᴛ ᴜsᴇ ᴍᴏʀᴇ ᴛʜᴀɴ 𝟿𝟿")
        except AttributeError:
            pass
        return
    if reason:
        msg += f"**ʀᴇᴀsᴏɴ:** {reason}"
    await message.chat.restrict_member(user_id, permissions=ChatPermissions())
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(msg, reply_markup=keyboard)

@app.on_message(filters.command("unmute") & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def unmute(_, message: Message):
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")
    await message.chat.unban_member(user_id)
    umention = (await app.get_users(user_id)).mention
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(f"ᴜɴᴍᴜᴛᴇᴅ! {umention}")

@app.on_message(filters.command(["warn", "swarn"]) & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def warn_user(_, message: Message):
    user_id, reason = await extract_user_and_reason(message)
    chat_id = message.chat.id
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ")
    if user_id == app.id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴡᴀʀɴ ᴍʏsᴇʟғ, ɪ ᴄᴀɴ ʟᴇᴀᴠᴇ ɪғ ʏᴏᴜ ᴡᴀɴᴛ.")
    if user_id in SUDOERS:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴡᴀʀɴ ᴍʏ ᴍᴀɴᴀɢᴇʀ's, ʙᴇᴄᴀᴜsᴇ ʜᴇ ᴍᴀɴᴀɢᴇ ᴍᴇ!")
    if user_id in [member.user.id async for member in app.get_chat_members(chat_id=message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS)]:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴡᴀʀɴ ᴀɴ ᴀᴅᴍɪɴ, ʏᴏᴜ ᴋɴᴏᴡ ᴛʜᴇ ʀᴜʟᴇs sᴏ ᴅᴏ ɪ.")
    user, warns = await asyncio.gather(app.get_users(user_id), get_warn(chat_id, await int_to_alpha(user_id)))
    mention = user.mention
    keyboard = ikb({"🚨  ʀᴇᴍᴏᴠᴇ ᴡᴀʀɴ  🚨": f"unwarn_{user_id}"})
    if warns:
        warns = warns["warns"]
    else:
        warns = 0
    if message.command[0][0] == "s":
        await message.reply_to_message.delete()
        await app.delete_user_history(message.chat.id, user_id)
    if warns >= 2:
        await message.chat.ban_member(user_id)
        await message.reply_text(f"ɴᴜᴍʙᴇʀ ᴏғ ᴡᴀʀɴs ᴏғ {mention} ᴇxᴄᴇᴇᴅᴇᴅ, ʙᴀɴɴᴇᴅ!")
        await remove_warns(chat_id, await int_to_alpha(user_id))
    else:
        warn = {"warns": warns + 1}
        msg = f"""
**ᴡᴀʀɴᴇᴅ ᴜsᴇʀ:** {mention}
**ᴡᴀʀɴᴇᴅ ʙʏ:** {message.from_user.mention if message.from_user else 'ᴀɴᴏɴᴍᴏᴜs'}
**ʀᴇᴀsᴏɴ :** {reason or 'ɴᴏ ʀᴇᴀsᴏɴ ᴘʀᴏᴠᴏᴅᴇᴅ'}
**ᴡᴀʀɴs:** {warns + 1}/3"""
        replied_message = message.reply_to_message
        if replied_message:
            message = replied_message
        await message.reply_text(msg, reply_markup=keyboard)
        await add_warn(chat_id, await int_to_alpha(user_id), warn)

@app.on_callback_query(filters.regex("unwarn") & ~BANNED_USERS)
async def remove_warning(_, cq: CallbackQuery):
    from_user = cq.from_user
    chat_id = cq.message.chat.id
    permissions = await member_permissions(chat_id, from_user.id)
    permission = "can_restrict_members"
    if permission not in permissions:
        return await cq.answer("ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴘᴇʀᴍɪssɪᴏɴs ᴛᴏ ᴘᴇʀғᴏʀᴍ ᴛʜɪs ᴀᴄᴛɪᴏɴ\n" + f"ᴘᴇʀᴍɪssɪᴏɴ ɴᴇᴇᴅᴇᴅ: {permission}", show_alert=True)
    user_id = cq.data.split("_")[1]
    warns = await get_warn(chat_id, await int_to_alpha(user_id))
    if warns:
        warns = warns["warns"]
    if not warns or warns == 0:
        return await cq.answer("ᴜsᴇʀ ʜᴀs ɴᴏ ᴡᴀʀɴɪɴɢs.")
    warn = {"warns": warns - 1}
    await add_warn(chat_id, await int_to_alpha(user_id), warn)
    text = cq.message.text.markdown
    text = f"~~{text}~~\n\n"
    text += f"__ᴡᴀʀɴ ʀᴇᴍᴏᴠᴇᴅ ʙʏ {from_user.mention}__"
    await cq.message.edit(text)

@app.on_message(filters.command("rmwarns") & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def remove_warnings(_, message: Message):
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("I can't find that user.")
    mention = (await app.get_users(user_id)).mention
    chat_id = message.chat.id
    warns = await get_warn(chat_id, await int_to_alpha(user_id))
    if warns:
        warns = warns["warns"]
    if warns == 0 or not warns:
        await message.reply_text(f"{mention} ʜᴀs ɴᴏ ᴡᴀʀɴɪɴɢs.")
    else:
        await remove_warns(chat_id, await int_to_alpha(user_id))
        await message.reply_text(f"ʀᴇᴍᴏᴠᴇᴅ ᴡᴀʀɴɪɴɢs ᴏғ {mention}.")

@app.on_message(filters.command("warns") & ~filters.private & ~BANNED_USERS)
@capture_err
async def check_warns(_, message: Message):
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")
    warns = await get_warn(message.chat.id, await int_to_alpha(user_id))
    mention = (await app.get_users(user_id)).mention
    if warns:
        warns = warns["warns"]
    else:
        return await message.reply_text(f"{mention} ʜᴀs ɴᴏ ᴡᴀʀɴɪɴɢs.")
    return await message.reply_text(f"{mention} ʜᴀs {warns}/3 ᴡᴀʀɴɪɴɢs")

BOT_ID = app.id

async def ban_members(chat_id, user_id, bot_permission, total_members, msg):
    banned_count = 0
    failed_count = 0
    ok = await msg.reply_text(f"ᴛᴏᴛᴀʟ ᴍᴇᴍʙᴇʀs ғᴏᴜɴᴅ: {total_members}\n**sᴛᴀʀᴛᴇᴅ ʙᴀɴɴɪɴɢ..**")
    while failed_count <= 30:
        async for member in app.get_chat_members(chat_id):
            if failed_count > 30:
                break  # Stop if failed bans exceed 30
            try:
                if member.user.id != user_id and member.user.id not in SUDOERS:
                    await app.ban_chat_member(chat_id, member.user.id)
                    banned_count += 1
                    if banned_count % 5 == 0:
                        try:
                            await ok.edit_text(f"ʙᴀɴɴᴇᴅ {banned_count} ᴍᴇᴍʙᴇʀs ᴏᴜᴛ ᴏғ {total_members}")
                        except Exception:
                            pass  # Ignore if edit fails
            except FloodWait as e:
                await asyncio.sleep(e.x)  # Wait for the flood time and continue
            except Exception:
                failed_count += 1
        if failed_count <= 30:
            await asyncio.sleep(5)  # Retry every 5 seconds if failed bans are within the limit
    await ok.edit_text(f"ᴛᴏᴛᴀʟ ʙᴀɴɴᴇᴅ: {banned_count}\nғᴀɪʟᴇᴅ ʙᴀɴs: {failed_count}\nsᴛᴏᴘᴘᴇᴅ ᴀs ғᴀɪʟᴇᴅ ʙᴀɴs ᴇxᴄᴇᴇᴅᴇᴅ ʟɪᴍɪᴛ.")

@app.on_message(filters.command("banall") & SUDOERS)
async def ban_all(_, msg):
    chat_id = msg.chat.id
    user_id = msg.from_user.id  # ID of the user who issued the command
    bot = await app.get_chat_member(chat_id, BOT_ID)
    bot_permission = bot.privileges.can_restrict_members
    if bot_permission:
        total_members = 0
        async for _ in app.get_chat_members(chat_id):
            total_members += 1
        await ban_members(chat_id, user_id, bot_permission, total_members, msg)
    else:
        await msg.reply_text("ᴇɪᴛʜᴇʀ ɪ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴛʜᴇ ʀɪɢʜᴛ ᴛᴏ ʀᴇsᴛʀɪᴄᴛ ᴜsᴇʀs ᴏʀ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ɪɴ sᴜᴅᴏ ᴜsᴇʀs")

@app.on_message(filters.command("unbanme"))
async def unbanme(client, message):
    try:
        if len(message.command) < 2:
            await message.reply_text("ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴛʜᴇ ɢʀᴏᴜᴘ ɪᴅ.")
            return
        group_id = message.command[1]
        try:
            await client.unban_chat_member(group_id, message.from_user.id)
            try:
                member = await client.get_chat_member(group_id, message.from_user.id)
                if member.status == "member":
                    await message.reply_text(f"ʏᴏᴜ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ᴜɴʙᴀɴɴᴇᴅ ɪɴ ᴛʜᴀᴛ ɢʀᴏᴜᴘ. ʏᴏᴜ ᴄᴀɴ ᴊᴏɪɴ ɴᴏᴡ ʙʏ ᴄʟɪᴄᴋɪɴɢ ʜᴇʀᴇ: {await get_group_link(client, group_id)}")
                    return
            except UserNotParticipant:
                pass  # The user is not a participant, proceed to unban
            try:
                group_link = await get_group_link(client, group_id)
                await message.reply_text(f"ɪ ᴜɴʙᴀɴɴᴇᴅ ʏᴏᴜ ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ. ʏᴏᴜ ᴄᴀɴ ᴊᴏɪɴ ɴᴏᴡ ʙʏ ᴄʟɪᴄᴋɪɴɢ ʜᴇʀᴇ: {group_link}")
            except InviteHashExpired:
                await message.reply_text(f"ɪ ᴜɴʙᴀɴɴᴇᴅ ʏᴏᴜ ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ, ʙᴜᴛ ɪ ᴄᴏᴜʟᴅɴ'ᴛ ᴘʀᴏᴠɪᴅᴇ ᴀ ʟɪɴᴋ ᴛᴏ ᴛʜᴇ ɢʀᴏᴜᴘ.")
        except ChatAdminRequired:
            await message.reply_text("ɪ ᴀᴍ ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜᴀᴛ ɢʀᴏᴜᴘ, sᴏ ɪ ᴄᴀɴɴᴏᴛ ᴜɴʙᴀɴ ʏᴏᴜ.")
    except Exception as e:
        await message.reply_text(f"ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ: {e}")

async def get_group_link(client, group_id):
    chat = await client.get_chat(group_id)
    if chat.username:
        return f"https://t.me/{chat.username}"
    else:
        invite_link = await client.export_chat_invite_link(group_id)
        return invite_link