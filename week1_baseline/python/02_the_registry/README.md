# 02 · The Tool Registry (Python)

Python port of the Ruby step 2 tool registry.

The Tool Registry is how BOUKENSHA manages what capabilities the agent can use.
It has two jobs:

1. storing tools
2. dispatching tools when asked

## New Files

| File | Description |
|---|---|
| `boukensha/registry.py` | The `Registry` class — registers tools and dispatches calls |
| `boukensha/errors.py` | BOUKENSHA-specific error classes |

## How It Works

The agent NEVER calls a tool directly. It emits a structured request (name and
args) and the Registry looks up the tool and runs it.

```
Agent:    "Hey registry call move with direction='north'"
Registry: "looking up 'move' in the tool table"
Registry: "Found it, now calling the block with the provided args"
Registry: "Here's the result"
Agent:    "Thanks buddy"
Registry: "That's why you pay me the big tokes"
```

## `boukensha.Registry`

| Method | Description |
|---|---|
| `tool(name, description, parameters=None, block=None)` | Registers a new tool on the context |
| `dispatch(name, args=None)` | Looks up a tool by name and calls it with the provided args |

## `boukensha.UnknownToolError`

Raised when `dispatch` is called with a name that has no registered tool. A
harness needs explicit error boundaries; an unrecognised tool name should never
silently fail.

```
UnknownToolError: No tool registered as 'flee'
```

## Considerations

`dispatch` unpacks the args mapping as keyword arguments onto the tool's callable.
In Ruby the equivalent step converts string keys to symbol keys, because the API
returns arguments as string-keyed JSON but Ruby blocks expect symbols. Python
keyword arguments are strings, so the translation is a no-op here — but it is a
real gotcha in the Ruby harness, kept visible for learning purposes.

## Expected Output

```
=== BOUKENSHA Step 2: Tool Registry ===

Config:  #<Boukensha::Config dir=.../.boukensha tasks=player>
Context: #<Context task=player turns=0 tools=2>
Tools:
  #<Tool name=move description=Move the player in a direction (north, so params=['direction']>
  #<Tool name=shout description=Shout a message so everyone in the zone can  params=['message']>

Dispatching 'shout' with message='dragon spotted'...
Result: DRAGON SPOTTED

Dispatching 'move' with direction='north'...
Result: You move north into a torch-lit corridor.

UnknownToolError caught: No tool registered as 'flee'
```

## Run Example

```bash
./week1_baseline/bin/python/02_the_registry
```

Or directly:

```bash
cd week1_baseline/python/02_the_registry
uv run python examples/example.py
```
