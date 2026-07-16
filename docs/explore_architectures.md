## Observations
- Each Bash call runs in a fresh shell, so a normal backgrounded nc connection would die between calls. The agent used run_in_background to keep nc and a FIFO-holder process alive persistently, then relayed commands in and read output out via the FIFO and a log file on each subsequent call.
- The agent ran into an issue when trying to write the memory files because the agent tried to Write the files without reading first.
- The server output for the agent was hard to read because it contains ANSI color codes and lots of white spaces.
- The agent backtracked a lot since there was no map provided.

## Technical Conclusion
Most of the trouble came from the agent hacking around the harness instead of
having the right tools for the job. A better setup would use an MCP server to
hold the game connection open properly, so the agent doesn't have to fake it
with pipes and background processes. It could also use a MUD SDK that speaks the
game's built-in data protocol to get clean, structured info instead of messy
colored text.