# EXPERIMENTAL MCP TARGETED FOR PUBLIC INBOX

A drafted small mcp used to summarize patch series and monitor the status.

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
