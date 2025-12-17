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
	"strconv"
	"strings"
	"time"

	"github.com/Laky-64/gologging"
	"github.com/amarnathcjd/gogram/telegram"

	"github.com/TeamAloneOp/AloneXMusic/internal/core"
	"github.com/TeamAloneOp/AloneXMusic/internal/database"
	"github.com/TeamAloneOp/AloneXMusic/internal/platforms"
	"github.com/TeamAloneOp/AloneXMusic/internal/state"
	"github.com/TeamAloneOp/AloneXMusic/internal/utils"
)

func cancelHandler(cb *telegram.CallbackQuery) error {
	var chatID int64
	opt := &telegram.CallbackOptions{Alert: true}

	chat, err := cb.GetChannel()
	if err != nil {
		cb.Answer("⚠️ Can’t access this chat.", opt)
		return telegram.EndGroup
	}

	chatID, err = utils.GetPeerID(cb.Client, chat.ID)
	if err != nil {
		cb.Answer("⚠️ Chat not recognized.", opt)
		return telegram.EndGroup
	}
	if cancel, ok := state.DownloadCancels[chatID]; ok {
		cancel()
		delete(state.DownloadCancels, chatID)
		cb.Answer("Download canceled.", &telegram.CallbackOptions{Alert: true})
	} else {
		cb.Answer("No download to cancel.", &telegram.CallbackOptions{Alert: true})
	}
	return telegram.EndGroup
}

func closeHandler(cb *telegram.CallbackQuery) error {
	cb.Answer("")
	cb.Delete()
	return telegram.EndGroup
}

func emptyCBHandler(cb *telegram.CallbackQuery) error {
	cb.Answer("")
	return telegram.EndGroup
}

func roomHandle(cb *telegram.CallbackQuery) error {
	logger := gologging.GetLogger("CALLBACK")

	var chatID int64
	opt := &telegram.CallbackOptions{Alert: true}
	data := string(cb.Data)

	var updateType string
	croom := false
	if strings.HasPrefix(data, "croom:") {
		updateType = strings.TrimPrefix(data, "croom:")
		croom = true
	} else if strings.HasPrefix(data, "room:") {
		updateType = strings.TrimPrefix(data, "room:")
	}

	if updateType == "" {
		logger.WarnF("Missing action in data: %s", data)
		if _, err := cb.Answer("⚠️ Invalid request.", opt); err != nil {
			logger.ErrorF("Answer error: %v", err)
		}
		return telegram.EndGroup
	}

	chat, err := cb.GetChannel()
	if err != nil {
		logger.ErrorF("GetChannel error: %v", err)
		if _, e := cb.Answer("⚠️ Can’t access this chat.", opt); e != nil {
			logger.ErrorF("Answer error: %v", e)
		}
		return telegram.EndGroup
	}

	chatID, err = utils.GetPeerID(cb.Client, chat.ID)
	if err != nil {
		logger.ErrorF("PeerID error for %d: %v", chatID, err)
		if _, e := cb.Answer("⚠️ Chat not recognized.", opt); e != nil {
			logger.ErrorF("Answer error: %v", e)
		}
		return telegram.EndGroup
	}

	var r *core.RoomState
	var ok bool
	if croom {
		realChatID, err := database.GetCPlayID(chatID)
		if err != nil {
			logger.ErrorF("Failed to get chat ID for cplay ID %d: %v", chatID, err)
			cb.Answer("⚠️ This channel isn't linked to any group.", opt)
			return telegram.EndGroup
		}
		chatID = realChatID
	}
	r, ok = core.GetRoom(chatID)
	if !ok || !r.IsActiveChat() {
		if _, err := cb.Answer("⚠️ Nothing playing right now.", opt); err != nil {
			logger.ErrorF("Answer error: %v", err)
		}
		if _, err := cb.Edit("🎵 Oops! The music is taking a break. Nothing’s playing at the moment."); err != nil {
			logger.ErrorF("Edit error: %v", err)
		}
		return telegram.EndGroup
	}
	if isAdmin, err := utils.IsChatAdmin(cb.Client, chatID, cb.SenderID); err != nil || !isAdmin {
		cb.Answer(
			"Only admins can do this actions.",
			opt,
		)
		return telegram.EndGroup
	}

	key := fmt.Sprintf("room:%d:%d", cb.Sender.ID, chatID)
	if remaining := utils.GetFlood(key); remaining > 0 {
		msg := fmt.Sprintf("⏳ Slow down! Try again in %.2f seconds.", remaining.Seconds())
		if _, err := cb.Answer(msg, opt); err != nil {
			logger.ErrorF("Flood Answer error: %v", err)
		}
		return telegram.EndGroup
	}
	utils.SetFlood(key, 5*time.Second)

	switch {
	case updateType == "pause":
		logger.InfoF("Callback → pause, chatID=%d", chatID)

		if r.IsMuted() {
			if _, err := cb.Answer("🔇 The chat is muted. Please unmute first.", opt); err != nil {
				logger.ErrorF("Answer error: %v", err)
			}
			return telegram.EndGroup
		}

		if r.IsPaused() {
			remaining := r.RemainingResumeDuration()
			if remaining > 0 {
				if _, err := cb.Answer(fmt.Sprintf("⏸️ Track is already paused — auto-resuming in %s.", formatDuration(int(remaining.Seconds()))), opt); err != nil {
					logger.ErrorF("Answer error: %v", err)
				}
			} else {
				if _, err := cb.Answer("⏸️ Track is already paused. Tap ▶️ Resume to continue.", opt); err != nil {
					logger.ErrorF("Answer error: %v", err)
				}
			}
			return telegram.EndGroup
		}

		if _, pauseErr := r.Pause(); pauseErr != nil {
			logger.ErrorF("Pause failed: %v", pauseErr)
			if _, err := cb.Answer("❌ Failed to pause playback.", opt); err != nil {
				logger.ErrorF("Answer error: %v", err)
			}
			return telegram.EndGroup
		}

		if _, err := cb.Answer(fmt.Sprintf("⏸️ Track paused at %s.", formatDuration(r.Position)), opt); err != nil {
			logger.ErrorF("Answer error: %v", err)
		}

		mention := utils.MentionHTML(cb.Sender)
		track := r.Track
		safeTitle := html.EscapeString(track.Title)

		msgText := fmt.Sprintf(
			"<b>⏸️ Track Paused</b>\n\n"+
				"<b>▫ Track:</b> <a href=\"%s\">%s</a>\n"+
				"<b>▫ Position:</b> %s / %s\n"+
				"<b>▫ Paused by:</b> %s",
			track.URL,
			utils.ShortTitle(safeTitle, 25),
			formatDuration(r.Position),
			formatDuration(track.Duration),
			mention,
		)

		if _, err := cb.Edit(msgText, &telegram.SendOptions{
			ParseMode:   "HTML",
			ReplyMarkup: core.GetPlayMarkup(r, false),
		}); err != nil {
			logger.ErrorF("Edit error: %v", err)
		}

	case updateType == "resume":
		logger.InfoF("Callback → resume, chatID=%d", chatID)

		if !r.IsPaused() {
			if _, err := cb.Answer("ℹ️ Track is already playing.", opt); err != nil {
				logger.ErrorF("Answer error: %v", err)
			}
			return telegram.EndGroup
		}

		if _, err := r.Resume(); err != nil {
			logger.ErrorF("Resume failed: %v", err)
			if _, e := cb.Answer("❌ Failed to resume playback.", opt); e != nil {
				logger.ErrorF("Answer error: %v", e)
			}
			return telegram.EndGroup
		}

		if _, err := cb.Answer(fmt.Sprintf("▶️ Resumed at %s.", formatDuration(r.Position)), opt); err != nil {
			logger.ErrorF("Answer error: %v", err)
		}

		mention := utils.MentionHTML(cb.Sender)
		track := r.Track

		msgText := fmt.Sprintf(
			"<b>🎵 Now Playing:</b>\n\n"+
				"<b>▫ Track:</b> <a href=\"%s\">%s</a>\n"+
				"<b>▫ Duration:</b> %s\n"+
				"<b>▫ Resumed by:</b> %s",
			track.URL,
			html.EscapeString(utils.ShortTitle(track.Title, 25)),
			formatDuration(track.Duration),
			mention,
		)

		if _, err := cb.Edit(msgText, &telegram.SendOptions{
			ParseMode:   "HTML",
			ReplyMarkup: core.GetPlayMarkup(r, false),
		}); err != nil {
			logger.ErrorF("Edit error: %v", err)
		}

	case updateType == "replay":
		logger.InfoF("Callback → replay, chatID=%d", chatID)

		mystic, err := cb.Respond("🔁 <b>Replaying current track...</b>")
		if err != nil {
			logger.ErrorF("Failed to send replay message: %v", err)
			return telegram.EndGroup
		}

		if err := r.Replay(); err != nil {
			logger.ErrorF("Replay failed: %v", err)
			utils.EOR(mystic, fmt.Sprintf("❌ <b>Replay Failed</b>\nError: <code>%v</code>", err))
			cb.Answer("❌ Failed to replay track.", opt)
			return telegram.EndGroup
		}
		track := r.Track

		trackTitle := html.EscapeString(utils.ShortTitle(track.Title, 25))
		totalDuration := formatDuration(track.Duration)

		msgText := fmt.Sprintf(
			"<b>🎵 Now Playing:</b>\n\n"+
				"<b>▫ Track:</b> <a href=\"%s\">%s</a>\n"+
				"<b>▫ Duration:</b> %s\n"+
				"<b>▫ Requested by:</b> %s\n"+
				"<b>▫ Replayed by:</b> %s",
			track.URL,
			trackTitle,
			totalDuration,
			track.BY,
			utils.MentionHTML(cb.Sender),
		)

		cb.Answer("🔁 Track replayed.", opt)

		optSend := &telegram.SendOptions{
			ParseMode:   "HTML",
			ReplyMarkup: core.GetPlayMarkup(r, false),
		}

		if track.Artwork != "" {
			optSend.Media = utils.CleanURL(track.Artwork)
		}

		mystic, _ = utils.EOR(mystic, msgText, *optSend)
		r.SetMystic(mystic)

		if _, err := cb.Edit(fmt.Sprintf("🔁 Track replayed by %s.", utils.MentionHTML(cb.Sender))); err != nil {
			logger.ErrorF("Edit error: %v", err)
		}

	case strings.HasPrefix(updateType, "seekback_"):
		parts := strings.Split(updateType, "_")
		seconds, err := strconv.Atoi(parts[1])
		if err != nil {
			cb.Answer("⚠️ Invalid seek value.", opt)
			return telegram.EndGroup
		}

		// Clamp to start
		if r.Position <= seconds {
			r.Seek(-int(r.Position))
		} else {
			r.Seek(-seconds)
		}

		cb.Answer(fmt.Sprintf("⏪ Sought back %d seconds", seconds), opt)
		rp(cb, fmt.Sprintf("⏪ Sought back %d seconds — by %s", seconds, utils.MentionHTML(cb.Sender)))

	case strings.HasPrefix(updateType, "seek_"):
		parts := strings.Split(updateType, "_")
		seconds, err := strconv.Atoi(parts[1])
		if err != nil {
			cb.Answer("⚠️ Invalid seek value.", opt)
			return telegram.EndGroup
		}

		// Warn if near end
		if (r.Track.Duration - r.Position) <= seconds {
			cb.Answer(fmt.Sprintf("⚠️ Cannot seek forward %d seconds — about to reach end.", seconds), opt)

			return telegram.EndGroup
		}

		r.Seek(seconds)
		cb.Answer(fmt.Sprintf("⏩ Sought %d seconds", seconds), opt)
		rp(cb, fmt.Sprintf("⏩ Sought %d seconds — by %s", seconds, utils.MentionHTML(cb.Sender)))

	case updateType == "skip":
		logger.InfoF("Callback → skip, chatID=%d", chatID)

		mention := utils.MentionHTML(cb.Sender)

		if len(r.Queue) == 0 && r.Loop == 0 {
			r.Destroy()
			msgText := fmt.Sprintf(
				"⏹️ <b>Playback stopped.</b>\nQueue is empty.\n\n▫ Skipped by: %s",
				mention,
			)
			if _, err := cb.Edit(msgText, &telegram.SendOptions{ParseMode: "HTML"}); err != nil {
				logger.ErrorF("Edit error: %v", err)
			}
			if _, err := cb.Answer("⏹️ Playback stopped — queue empty.", opt); err != nil {
				logger.ErrorF("Answer error: %v", err)
			}
			return telegram.EndGroup
		}

		t := r.NextTrack()

		mystic, err := cb.Respond("📥 Downloading your next track...")
		if err != nil {
			logger.ErrorF("Failed to send msg: %v", err)
		}

		path, err := platforms.Download(context.Background(), t, mystic)
		if err != nil {
			logger.ErrorF("Download failed for %s: %v", t.URL, err)
			utils.EOR(mystic, "❌ Failed to download next track.")
			if _, err := cb.Answer("❌ Failed to download next track.", opt); err != nil {
				logger.ErrorF("Answer error: %v", err)
			}
			return telegram.EndGroup
		}

		if err := r.Play(t, path); err != nil {
			logger.ErrorF("Play error: %v", err)
			utils.EOR(mystic, "❌ Failed to play next track.")
			if _, err := cb.Answer("❌ Failed to play next track.", opt); err != nil {
				logger.ErrorF("Answer error: %v", err)
			}
			return telegram.EndGroup
		}

		if _, err := cb.Answer("⏭️ Track skipped.", opt); err != nil {
			logger.ErrorF("Answer error: %v", err)
		}

		_, err = cb.Delete()
		if err != nil {
			logger.ErrorF("Delete error: %v", err)
		}

		title := utils.ShortTitle(t.Title, 25)
		safeTitle := html.EscapeString(title)
		msgText := fmt.Sprintf(
			"<b>🎵 Now Playing:</b>\n\n"+
				"<b>▫ Track:</b> <a href=\"%s\">%s</a>\n"+
				"<b>▫ Duration:</b> %s\n"+
				"<b>▫ Requested by:</b> %s",
			t.URL,
			safeTitle,
			formatDuration(t.Duration),
			t.BY,
		)

		opt := &telegram.SendOptions{
			ParseMode:   "HTML",
			ReplyMarkup: core.GetPlayMarkup(r, false),
		}

		if t.Artwork != "" {
			opt.Media = utils.CleanURL(t.Artwork)
		}

		mystic, _ = utils.EOR(mystic, msgText, *opt)

		if _, err := mystic.Reply(fmt.Sprintf("⏭️ Skipped by %s", mention)); err != nil {
			logger.ErrorF("Reply error: %v", err)
		}
		r.SetMystic(mystic)
		return telegram.EndGroup

	case updateType == "stop":

		logger.InfoF("Callback → stop, chatID=%d", chatID)

		r.Destroy()

		if _, err := cb.Answer("⏹️ Playback stopped.", opt); err != nil {
			logger.ErrorF("Answer error: %v", err)
		}

		if _, err := cb.Edit(fmt.Sprintf("⏹️ Playback stopped and cleared by %s.", utils.MentionHTML(cb.Sender))); err != nil {
			logger.ErrorF("Edit error: %v", err)
		}

	default:
		logger.WarnF("Unknown callback type: %s", updateType)
		if _, err := cb.Answer("⚠️ Unknown action.", opt); err != nil {
			logger.ErrorF("Answer error: %v", err)
		}
	}

	return telegram.EndGroup
}

func rp(c *telegram.CallbackQuery, t string) {
	msg, err := c.GetMessage()
	if err != nil {
		return
	}

	msg.Reply(t)
}
