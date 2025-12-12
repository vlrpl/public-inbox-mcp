# Series Review Instructions

This MCP prompt is designed to review a series of patches from a mailing list. The review process involves finding, retrieving, and analyzing patch series using notmuch tools.

## Overview

The model will review a series by:
1. Finding the exact series using a notmuch query
2. Retrieving the complete series (cover letter + patches)
3. Performing deep analysis on each email in the series

## Required Process

### Step 1: Find the Series

Use the `mcp.tool find_thread()` with the following notmuch query provided by the user as a parameter:

{notmuch_filter}

**Important Requirements:**
- The tool MUST return exactly **one series** (not zero, not multiple)
- If zero or multiple series are returned, the process cannot continue
- The returned data will contain a thread ID needed for the next step

### Step 2: Retrieve the Complete Series

Once the series is found, use the thread ID to invoke `mcp.tool show_series()`.

This tool returns:
- The cover letter of the series
- All patches in the series

### Step 3: Parse the Series Format

The returned data has the following structure:

```
[Metadata for cover letter]
Message-ID: <message-id>
In-Reply-To: <in-reply-to>
From: <sender>
To: <recipient>
Cc: <cc-list>

[Cover letter content]

---

[Metadata for patch 1]
Message-ID: <message-id>
In-Reply-To: <in-reply-to>
From: <sender>
To: <recipient>
Cc: <cc-list>

[Patch 1 content]

---

[Metadata for patch 2]
...
```

**Key Points:**
- Each section (cover letter and patches) is separated by a series of dashes (`---`)
- Each section begins with metadata including:
  - Message-ID
  - In-Reply-To
  - From
  - To
  - Cc
- The content follows after the metadata

### Step 4: Deep Dive Analysis

For each email in the series (cover letter and patches):

1. **Load the analysis prompt**: Use the prompt located at `{review_prompts_path}`

2. **Run analysis**: Execute a deep dive analysis of the patch content using the loaded prompt

3. **Leverage code context**:
   - You are operating under the tree where the patch applies
   - You have access to the codebase for additional context and understanding
   - Use this access to provide more informed analysis

## Analysis Guidelines

When analyzing each patch:
- Examine the code changes in detail
- Consider the impact on the existing codebase
- Look for potential issues, improvements, or concerns
- Reference related code files when necessary for context
- Provide constructive feedback based on the patch content and surrounding code

## Error Handling

- If `find_thread()` returns zero results: Report that no series was found for the given query
- If `find_thread()` returns multiple results: Report that multiple series were found and request a more specific query
- If `show_series()` fails: Report the error and cannot proceed with analysis
- If the user-defined prompt cannot be loaded: Report the issue and request a valid prompt path

## Output Format

Provide a comprehensive review that includes:
1. Series overview (from cover letter analysis)
2. Individual patch analysis for each patch
3. Overall series assessment
4. Any recommendations or concerns

Remember: The goal is to provide thorough, constructive feedback on the patch series using both the patch content and available codebase context.
