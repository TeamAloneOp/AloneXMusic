package ubot

import "github.com/TeamAloneOp/AloneXMusic/ntgcalls"

func (ctx *Context) Calls() map[int64]*ntgcalls.CallInfo {
	return ctx.binding.Calls()
}
