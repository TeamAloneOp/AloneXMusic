/*
 * This file is part of AloneXMusic.
 *
 * AloneXMusic — A Telegram bot that streams music into group voice chats with seamless playback and control.
 * Copyright (C) 2025 TeamAloneOp
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 */
package modules

import (
	"context"
	"fmt"
	"html"

	"github.com/Laky-64/gologging"
	"github.com/amarnathcjd/gogram/telegram"

	"github.com/TeamAloneOp/AloneXMusic/internal/core"
	"github.com/TeamAloneOp/AloneXMusic/internal/database"
	"github.com/TeamAloneOp/AloneXMusic/internal/platforms"
	"github.com/TeamAloneOp/AloneXMusic/internal/utils"
	"github.com/TeamAloneOp/AloneXMusic/ntgcalls"
)

func onStreamEndHandler(chatID int64, streamType ntgcalls.StreamType, streamDevice ntgcalls.StreamDevice) {
	r, ok := core.GetRoom(chatID)
	if !ok {
		return
	}
	r.Parse()
	if r.IsCPlay() {

		cid, err := database.GetChatIDFromCPlayID(chatID)
		if err != nil {

			core.Bot.SendMessage(chatID, "⚠️ Failed to get your connected channel's ID")
			r.Destroy()
			return
		}

		chatID = cid

	}
	if len(r.Queue) == 0 && r.Loop == 0 {
		r.Destroy()
		core.Bot.SendMessage(chatID, "🎵 <b>Queue Finished!</b>\n\nNo more songs to play. Use /play to add more tracks! 🎶")
		return
	}

	t := r.NextTrack()

	mystic, err := core.Bot.SendMessage(chatID, "📥 Downloading your next track...")
	if err != nil {
		gologging.ErrorF("[call.go] Failed to send msg: %v", err)
	}

	filePath, err := platforms.Download(context.Background(), t, mystic)
	if err != nil {
		gologging.ErrorF("Download failed for %s: %v", t.URL, err)
		utils.EOR(mystic, fmt.Sprintf("❌ Failed to download.\nError: %v\nUse /skip to skip playback", err))
		return
	}
	if err := r.Play(t, filePath); err != nil {
		utils.EOR(mystic, "❌ Failed to play song.")
		return
	}

	title := utils.ShortTitle(t.Title, 25)
	safeTitle := html.EscapeString(title)

	msgText := fmt.Sprintf(
		"<b>🎵 Now Playing:</b>\n\n<b>▫ Track:</b> <a href=\"%s\">%s</a>\n<b>▫ Duration:</b> %s\n<b>▫ Requested by:</b> %s",
		t.URL,
		safeTitle,
		formatDuration(t.Duration),
		t.BY,
	)
	opt := telegram.SendOptions{
		ParseMode:   "HTML",
		ReplyMarkup: core.GetPlayMarkup(r, false),
	}

	if t.Artwork != "" {
		opt.Media = utils.CleanURL(t.Artwork)
	}

	mystic, _ = utils.EOR(mystic, msgText, opt)
	r.SetMystic(mystic)
}
