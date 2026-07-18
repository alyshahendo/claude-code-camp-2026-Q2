# Preweek Technical Documentation

## Technical Goal
Determine which agent architectures fit the business use case, and how well each one fits.

Different types of agent architectures we've explored:

1. An agent file with referenced files: 
    - a CLAUDE.md prompt 
    - Markdown memory files (`data/player.md`, `data/world.md`)
    - Agent connecting to the MUD over raw Netcat
2. Agent Skills driven by the main agent:
    - `play-mud` skill 
    - Persistent connection daemon (`mud.py`) 
    - Memory files (`player.md` / `world.md` / `goals.md`).

The goal for the agent itself is to play tbaMUD on the player's behalf. Specifically, to level up enough to defeat the Massive Minotaur in the Newbie Zone.


## Technical Uncertainty
- I am uncertain that a coding harness can navigate the game world and manage its own memory well enough to meet the goal. It is built for editing code, not for playing a long running, stateful game.
- I am uncertain that the agent won't take shortcuts. Since it is a coding agent, it may look at the game's source code on disk instead of following the prompt and playing the game.
- Can the agent hold a persistent connection to the MUD, or does connection management need to live outside the agent?
- I don't know where the capability boundaries sit. At what point does a prompt file or skill stop being enough?


## Technical Hypothesis
- Architecture 1 (Agent + memory files):
    - Connection: the agent will struggle to hold a persistent connection, because each Bash call runs in a fresh shell and the coding harness is not built to keep a socket alive between calls.
    - Navigation and memory: a plain agent file with referenced memory files would still be enough to navigate the world and track its own state well enough to make progress toward the goal.
    - Shortcuts: the agent will follow the prompt and play the game rather than reading the game's source on disk.
- Architecture 2 (Agent skill + daemon + memory files):
    - Connection: packaging the workflow as a skill with a persistent daemon fixes part 1's connection problem, so a single character session stays alive across many commands.
    - Navigation and memory: session memory files carry state across sessions, so the agent resumes its goal instead of rediscovering the map.
    - Shortcuts and capability boundary: the skill's instructions would be enough to keep the agent playing the game properly, without taking shortcuts. In other words, a prompt plus a script is a high enough rung on the capability ladder for this task.
- Underlying assumption for both: giving the agent the right instructions is sufficient, and the agent will follow the rules of play it's given.

## Technical Observations

### 1. Agent file with referenced files
- Each Bash call runs in a fresh shell, so a normal backgrounded `nc` connection would die between calls. Dropping the connection dumps the character back at the starting altar, losing position, combat, and buffs, so a fresh login per command meant no real progress was possible.
- The agent worked around the fresh shell problem instead of solving it. It ran `nc` as a background process so the connection stayed open, then sent commands to it and read the game's replies from a log file on each later call. It worked, but it was fragile plumbing the agent had to invent and babysit.
- The agent hit an issue writing the memory files because it tried to Write files without reading them first. The harness enforces read before write, and the agent lost turns discovering this rule by tripping over it.
- The server output was hard for the agent to read because of ANSI color codes and lots of whitespace. The agent spent effort parsing noise instead of playing, and sometimes misread room descriptions and prompts.
- The agent backtracked a lot since there was no map provided. 

### 2. Agent Skills 
- The skill's persistent daemon solved the connection problem from part 1. No more hacks.
- The session memory files worked. The agent read them first, resumed the prior session's goal, and checkpointed changes as it played.
- The skill's instructions were followed for mechanics but not judgment. The agent ran the perceive, decide, act, verify loop and kept the memory files current, but the guidance to `consider` targets and respect danger did not stick.
- The agent still lacked game sense. It ignored repeated zone level warnings, died to the Black King at level 1, and later got stuck in pitch black rooms with no light source. It ended the session still at level 1 with 0 gold and the primary goal marked BLOCKED.
- When the path inside the game was blocked, the agent read the CircleMUD world code on disk to find the Red Room (room #18629) and the Minotaur's stats (level 7, roughly 100 damage per hit) instead of discovering them by playing. Nothing in the setup prevented this: the world files sit in the same repo the agent works in, and a skill cannot take Read access away.


## Technical Conclusions
- Architecture 1's trouble mostly came from the agent hacking around the harness instead of having the right tools. A better setup would hold the game connection open in a dedicated session layer and return clean structured data instead of messy colored text.
- A skill is sufficient for the mechanics of the task but not the play of it. It fixed part 1's plumbing, but a skill is just instructions plus a script and cannot enforce its own rules. The agent ignored its guidance when convenient.
- A task like this needs an enforcing layer that validates actions and is the only door into the game.

## Key Takeaways
- Persistent state (connections and memory) is going to be a problem for any long running agent.
- Clean, structured output matters as much as good instructions.
- Instructions guide behavior but don't constrain it. The boundaries need to be enforced via a tool as opposed to via a prompt.
- We should try building our own agentic loop as the next iteration and test its efficacy against the other architectures we've tried.
