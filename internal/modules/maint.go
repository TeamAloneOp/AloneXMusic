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
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/amarnathcjd/gogram/telegram"

	"github.com/TeamAloneOp/AloneXMusic/internal/core"
	"github.com/TeamAloneOp/AloneXMusic/internal/database"
	"github.com/TeamAloneOp/AloneXMusic/internal/utils"
)

var maintenanceCancel = struct {
	sync.Mutex
	cancel bool
}{}

func handleMaintenance(m *telegram.NewMessage) error {
	args := strings.Fields(m.Text())
	current, err := database.IsMaintenance()
	if err != nil {
		m.Reply("❌ Failed to check maintenance status: " + err.Error())
		return telegram.EndGroup
	}

	if len(args) < 2 {

		status := "🔴 Disabled"
		if current {
			if reason, rerr := database.GetMaintReason(); rerr == nil && reason != "" {
				status = fmt.Sprintf("🟢 Enabled\n📝 Reason: %s", reason)
			} else {
				status = "🟢 Enabled"
			}
		}

		m.Reply(fmt.Sprintf(
			"⚙️ Usage: %s [<code>enable</code>|<code>disable</code>] [reason]\n\n📜 Current status: %s",
			getCommand(m),
			status,
		))
		return telegram.EndGroup
	}

	enable, err := utils.ParseBool(args[1])
	if err != nil {
		m.Reply("⚠️ Invalid option. Use 'enable' or 'disable'.")
		return telegram.EndGroup
	}
	reason := strings.Join(args[2:], " ")

	oldReason, _ := database.GetMaintReason()

	if current == enable {
		if enable {
			switch {
			case reason == oldReason:
				m.Reply("ℹ️ Maintenance mode is already enabled with the same reason.")
				return telegram.EndGroup
			case reason == "" && oldReason != "":
				_ = database.SetMaintenance(true, "")
				m.Reply("✅ Maintenance reason removed successfully.")
				return telegram.EndGroup
			case reason != "" && reason != oldReason:
				_ = database.SetMaintenance(true, reason)
				m.Reply(fmt.Sprintf("✅ Maintenance reason updated successfully.\n📝 Reason: %s", reason))
				return telegram.EndGroup
			default:
				m.Reply("ℹ️ Maintenance mode is already enabled 🟢.")
				return telegram.EndGroup
			}
		} else {
			m.Reply("ℹ️ Maintenance mode is already disabled 🔴.")
			return telegram.EndGroup
		}
	}

	_ = database.SetMaintenance(enable, reason)
	logger.InfoF("User %d set maintenance mode to %v. Reason: %s", m.SenderID(), enable, reason)

	if enable {
		maintenanceCancel.Lock()
		maintenanceCancel.cancel = false
		maintenanceCancel.Unlock()

		go func(c *telegram.Client, reason string) {
			for _, id := range core.GetAllRoomIDs() {
				maintenanceCancel.Lock()
				if maintenanceCancel.cancel {
					maintenanceCancel.Unlock()
					break
				}
				maintenanceCancel.Unlock()

				if r, ok := core.GetRoom(id); ok {

					r.Destroy()
					if reason != "" {
						c.SendMessage(id, "⚠️ Bot is entering maintenance mode.\n📝 Reason: "+reason)

						time.Sleep(1 * time.Second)
					}
				}
			}
		}(m.Client, reason)

		msg := "✅ Maintenance mode enabled successfully."
		if reason != "" {
			msg += fmt.Sprintf("\n📝 Reason: %s", reason)
		}
		m.Reply(msg)
		return telegram.EndGroup
	}

	maintenanceCancel.Lock()
	maintenanceCancel.cancel = true
	maintenanceCancel.Unlock()

	m.Reply("✅ Maintenance mode disabled successfully.")
	return telegram.EndGroup
}
