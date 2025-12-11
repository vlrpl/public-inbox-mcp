# EXPERIMENTAL MCP TARGETED FOR PUBLIC INBOX

A drafted small mcp used to summarize patch series and monitor the status.
Code and prompts are mostly vibe-coded.

## NOTMUCH CONFIGURATION

Add the List header to the config and reindex, if needed:

```
notmuch config index.header.List=List-Id
notmuch reindex <search-term>
```

## NOTMUCH HOOKS

### PRE

```
lei up --all
```

### POST

```
notmuch tag -new +netdev -- List:netdev.vger.kernel.org
```
