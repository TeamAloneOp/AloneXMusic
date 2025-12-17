package types

import "github.com/TeamAloneOp/AloneXMusic/ntgcalls"

type PendingConnection struct {
	MediaDescription ntgcalls.MediaDescription
	Payload          string
	Presentation     bool
}
