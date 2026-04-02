# red-cogs

Custom [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot) cogs by Joka.ca.

## Installation

```
[p]repo add joka-cogs https://github.com/orangezef/red-cogs
[p]cog install joka-cogs <cog_name>
[p]load <cog_name>
```

## Cogs

### AutoDelete

Universally auto-deletes bot messages after the guild's configured `[p]set deletedelay`. Red's built-in delete_delay only removes the user's command message — it does not delete the bot's response, especially for slash commands and interaction responses. This cog fills that gap.

**Why this exists:** Red core's `delete_delay` misses slash command responses, interaction replies, and text command responses from many third-party cogs. Without this cog, bot responses from `/tts`, `/play`, casino games, and other slash-enabled cogs pile up in channels permanently.

#### Features

- Listens for all bot messages and deletes them after the guild's configured delay
- Works for slash commands, interactions, and text command responses
- Per-channel exclusion list (protect starboard, modlog, announcements, etc.)
- Safe task cancellation on cog unload — no orphaned deletions
- Fail-safe error handling — if config can't be read, messages are preserved (not deleted)
- Flood protection — 1000 pending task ceiling
- Granular logging — permission errors and failures are logged, not silently swallowed

#### Commands

| Command | Permission | Description |
|---------|-----------|-------------|
| `[p]autodelete exclude #channel` | Admin / Manage Server | Exclude a channel from auto-deletion |
| `[p]autodelete include #channel` | Admin / Manage Server | Re-include a previously excluded channel |
| `[p]autodelete list` | Admin / Manage Server | List all excluded channels |
| `[p]autodelete prune` | Admin / Manage Server | Remove deleted channels from the exclusion list |

#### Setup

1. Install and load the cog
2. Set your guild's delete delay: `[p]set deletedelay 60` (max 60 seconds)
3. Exclude channels that should keep messages permanently:
   ```
   [p]autodelete exclude #starboard
   [p]autodelete exclude #mod-log
   ```

#### Safety

This cog has been through multiple security reviews. Key guarantees:

- **Only deletes its own messages.** The bot checks `message.author.id == bot.user.id` before any deletion. This check is evaluated before any async work — there is no race condition.
- **Cannot delete other users' messages.** The `message.delete()` call is bound to the specific message object that passed the author check. Discord message IDs are immutable and never reused.
- **No special permissions required.** Discord allows any user/bot to delete their own messages without Manage Messages permission.
- **Fails safe.** If the exclusion list or delay config can't be read, the cog skips deletion rather than deleting anyway.
- **Clean unload.** All pending deletion tasks are cancelled when the cog is unloaded or reloaded.

#### Requirements

- Red-DiscordBot >= 3.5.0
- Python >= 3.10
- Guild must have `[p]set deletedelay` configured (default is -1 / disabled)

## License

MIT
