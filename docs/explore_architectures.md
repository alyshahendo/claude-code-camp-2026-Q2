# Explore Agent Architecture

## 1. An agent file with referenced files

### Observations
- Each Bash call runs in a fresh shell, so a normal backgrounded nc connection would die between calls. The agent used run_in_background to keep nc and a FIFO-holder process alive persistently, then relayed commands in and read output out via the FIFO and a log file on each subsequent call.
- The agent ran into an issue when trying to write the memory files because the agent tried to Write the files without reading first.
- The server output for the agent was hard to read because it contains ANSI color codes and lots of white spaces.
- The agent backtracked a lot since there was no map provided.

### Technical Conclusion
Most of the trouble came from the agent hacking around the harness instead of
having the right tools for the job. A better setup would use an MCP server to
hold the game connection open properly, so the agent doesn't have to fake it
with pipes and background processes. It could also use a MUD SDK that speaks the
game's built-in data protocol to get clean, structured info instead of messy
colored text.

## 2. Agent Skills drive by main agent eg. ~/skills

Agent Skills are portable, reusable instructions that equip an agent with specialized capabilities and repeatable workflows. They follow an open standard supported by many coding agents and SDKs.

### Observations
- The skill's persistent daemon (mud.py) solved the connection problem from part 1. The agent issued short `send` calls against one logged-in session instead of hacking around fresh shells.
- The session memory files (player.md / world.md / goals.md) worked. The agent read them first, resumed the prior session's goal, and checkpointed changes as it played.
- The agent still lacked game sense. It ignored repeated zone level warnings, died to the Black King at level 1, and later got stuck in pitch black rooms with no light source.
- When the in game path was blocked, the agent read the CircleMUD world code on disk to find the Red Room and Minotaur stats instead of discovering them by playing.

### Technical Conclusion
A skill is sufficient for the mechanics of this task but not the play of it. It
fixed part 1's plumbing, but a skill is just instructions plus a blanket python
script and cannot enforce its own rules. The agent ignored its guidance when
convenient and read the CircleMUD world code on disk to find destinations instead
of playing the game. A task like this needs an enforcing layer, such as the
mud_manager primitives or an MCP server, that validates actions and is the only
door into the game.