---
name: play-mud
description: >-
  Play the CircleMUD/tbaMUD text adventure running at localhost:4000 as the
  character `dummy`. Use this skill whenever the user wants to connect to,
  log into, explore, or play the MUD — moving between rooms, fighting mobs,
  leveling up, practicing skills, healing, shopping, or pursuing a goal like
  "beat the Massive Minotaur in the Newbie Zone." Trigger it for any request
  phrased as "play the MUD", "connect to the MUD", "keep leveling", "go fight
  X", "what's in this room", "check my score", or anything that means sending
  game commands and reading the game's response. The skill manages a persistent
  logged-in session so gameplay state survives across many commands.
---

# Play MUD

Play the CircleMUD running at `localhost:4000` as the character **dummy**
(password **helloworld**). This skill gives you a persistent, logged-in
connection and the game knowledge to make progress.

## Why a persistent session (read this first)

The MUD is stateful: your character stands in a room, and every command
mutates that live state. If the connection drops between commands, the game
dumps you back at the starting altar and you lose your position, combat, and
buffs. A plain `nc localhost 4000` closes the moment a shell command returns —
so it re-logs-in every time and never makes real progress.

`scripts/mud.py` solves this with a background **daemon** that holds one socket
and stays logged in. You issue many short `send` calls across many tool calls,
but a single character session stays alive the whole time. It's pure Python
stdlib — no install step.

## Quickstart

```sh
cd <this-skill-dir>          # so ./scripts/mud.py resolves

python3 scripts/mud.py start          # connect + log in (idempotent, safe to re-run)
python3 scripts/mud.py send "look"    # send a command, get the game's reply
python3 scripts/mud.py send "score"   # check HP/mana/move/exp/level
python3 scripts/mud.py read           # drain async chatter (fights, arrivals) with no command
python3 scripts/mud.py status         # JSON: is the daemon up and logged in?
python3 scripts/mud.py transcript     # full raw session log so far
python3 scripts/mud.py stop           # end the session
```

Always run `start` first (it no-ops if already running). If a `send` prints
`no daemon running`, the daemon died — just `start` again.

### How commands work

- `send "<command>"` writes the command and returns everything the server
  sends back until ~0.4s of silence (the end-of-reply signal). This is
  prompt-format-agnostic, so it works during combat spam too.
- Occasionally a stray async line (someone shouting, a mob wandering in) is
  bundled into a reply — that's intended and lossless, better than losing it.
- For long or slow output (big `help` files, heavy combat rounds) raise the
  window: `send "help spells" --timeout 15 --quiet 0.8`.
- `read` sends nothing; it just collects async output that arrived since your
  last call — poll it during combat to see each round.
- Everything, async included, is appended to the transcript, so nothing is
  ever truly lost even if a live read misses it.

## The playing loop

Play in a perceive → decide → act → verify loop:

1. **Perceive** — `look` for the room (exits, mobs, objects), `score` for your
   vitals. Keep a running note of where you are; the world is a graph of rooms
   connected by exits (`n e s w u d`).
2. **Decide** — pick the next action toward the goal (see below).
3. **Act** — `send` the command.
4. **Verify** — read the reply. Did you move? Did the fight start? Did HP drop?
   Re-`look` or `score` when unsure. Never assume a command worked — confirm.

This loop runs on top of the **session memory** described next — read it at the
start, and checkpoint what you learn as you go.

## Session memory (read at start, update as you play)

The game session is ephemeral, but progress toward a goal often spans many
commands and even multiple play sessions with fresh context. Three files under
`week0_explore/explore_architecture/002_agent_skills/data/` are your durable
memory — treat them the way you'd treat notes you left for your future self:

- **`data/player.md`** — a snapshot of the character: class, level, vitals, exp
  and exp-to-next, gold, location, inventory, equipment, skills practiced.
- **`data/world.md`** — everything learned about the world: the room map with
  exits, notable locations (guilds, shops, the fountain, the Inn), shop
  inventories, and mobs seen with their danger level.
- **`data/goals.md`** — the mission log: each long-horizon goal (e.g. "reach
  level 10", "defeat the Massive Minotaur") with its status, a sub-step plan,
  and a dated progress log of what you've tried and what worked.

**At the start of a session, read all three first.** They tell you who the
character is, where things are, and what you were in the middle of — so you
resume the plan instead of rediscovering the map and repeating dead ends.

**Update them the moment something durable changes** — don't batch it to the
end, because a session can be cut off mid-task:

- Leveled up, gained/spent gold, changed gear, practiced a skill, moved rooms →
  update `player.md`.
- Discovered a new room/exit, a shop's stock, or a mob's `consider` result →
  update `world.md`.
- Made or abandoned progress on a goal → append a dated line to that goal's
  progress log in `goals.md`, and tick its sub-steps. This is what makes long
  goals survive a context reset: the next session reads the log and continues.

The bar to aim for: if this conversation ended right now and a fresh session
started, these three files alone should be enough to pick the goal back up
without losing meaningful ground.

## Combat & survival

- **Assess before you swing:** `consider <mob>` tells you how dangerous a
  target is. Fight things it calls easy/manageable; avoid "you can't win".
  Never attack a `cityguard` or other town NPC — they will kill you.
- **Attack:** `kill <mob>` (or `hit <mob>`). Combat is auto-rounds; poll
  `read` (or send `score`) between rounds to watch HP.
- **Watch HP obsessively.** `score` shows `24(24) hit` = current(max). If HP
  gets low, `flee` to escape, then heal.
- **Heal by resting:** `rest` or `sleep` regenerates HP/mana/move much faster
  than standing. `sleep` is fastest but you're vulnerable and blind; `wake`
  then `stand` to get up. Heal to full between fights.
- **Set a safety net:** `wimpy 10` makes you auto-flee when HP drops below 10.
- **Loot:** after a kill, `get all corpse` then `get all` / take coins.
- **Eat & drink:** the character starts hungry and thirsty — buy food/water or
  `drink` from a fountain (e.g. the Temple Square fountain) so stats don't suffer.

## Leveling up

`score` shows exp and "You need N exp to reach your next level." Gain exp by
killing mobs you can handle. To get stronger:

- **Find your guild and practice.** Guilds teach skills/spells. From
  `HOW_TO_PLAY.md`: Warriors' Guild is east of Main Street (south side);
  Mages' west Main Street (south side); Clerics' west of Temple Square;
  Thieves' south of the Dark Alley. At your guild, `practice` lists what you
  can learn; `practice kick` (etc.) improves a skill. Higher % = more reliable.
- **Learn your class:** `help warrior` / `help mage` / etc., and `help
  practice`, `help spells`, `help experience`.
- **Grind safe mobs**, heal between fights, repeat. Level up before taking on
  anything tough.

## The primary challenge

**Level up enough to defeat the Massive Minotaur in the Newbie Zone**
(`CHALLENGES.md`). Strategy: practice your class skills at your guild, grind
weaker Newbie Zone mobs to level up and sharpen skills, keep gear and HP
topped up, and only engage the Minotaur once `consider` says you stand a
chance. Retreat with `flee` if a fight turns bad — a live low-level character
beats a dead one.

## Orienting in Midgaard (starting area)

You start in/near the Temple of Midgaard. Landmarks from `HOW_TO_PLAY.md`:
Temple (bank — check balance), Reading Room (bulletin board), Temple Square
(fountain to drink), Market Square (shops, south of Temple Square). Map as you
go with pencil-and-paper discipline: note each room and its exits so you can
navigate back. If you get lost, remember `quit`/re-entry returns you to the
altar — use `offer` then `rent` at an Inn to save your location first.

## Reference & internals

- **`scripts/mud.py`** — the whole connection layer (daemon + client). Read its
  module docstring to understand the design; tweak defaults via `--host
  --port --user --password` flags or `MUD_HOST`/`MUD_PORT`/`MUD_USER`/`MUD_PASS`
  env vars.
- **`week0_explore/HOW_TO_PLAY.md`** — running the server via Docker, the full
  command-learning checklist, and area details.
- **`week0_explore/mud_manager/`** — a Ruby gem with a battle-tested `Session` and a
  typed `Primitives` command surface (validated `move`, `attack`, `cast`,
  `consider`, `shop`, `bank`, …). Consult `lib/mud_manager/primitives.rb` as a
  catalog of every player command and its exact argument shape.

## Troubleshooting

- **`daemon did not become ready`** — the MUD may be down. Check with
  `nc -z localhost 4000`; start it via `week0_explore/infrastructure`
  (`docker compose up --build`). Then inspect the daemon log printed in the
  error, or `transcript` for where login stalled.
- **`no daemon running` on send** — the daemon exited; run `start` again.
  Session state resets to the altar unless you had `rent`-saved.
- **Replies look empty or truncated** — raise `--timeout` and `--quiet`; slow
  or large responses need a wider window.
- **Wrong password / stuck at login** — the login dance in `mud.py` assumes an
  existing character. If `dummy` doesn't exist yet, create it once via
  `nc localhost 4000` (see `HOW_TO_PLAY.md`), then use the skill.
