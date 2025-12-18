# Changelog Generator

Generate a technical development changelog by analyzing the differences between two git objects using git range-diff.

## Parameters
- `{gitobject}`: The first git object (SHA1, branch, or tag) - typically the previous version
- `{gitobject-next}`: The second git object (SHA1, branch, or tag) - the new version to generate changelog for

## Process

First, perform a git range-diff to analyze the changes between the two versions:

```bash
git range-diff {gitobject}^! {gitobject-next}^!
```

## Understanding git range-diff Output

The `git range-diff` command shows **differences between two versions of a patch series** by finding pairs of commits from both ranges that correspond with each other. It produces a diff-of-diffs that compares how patches changed between versions, not just the final content.

### Commit Correspondence Symbols

Range-diff first shows how commits map between the two ranges using these symbols:

- `-:  ------- > 1:  0ddba11` - **New commit added** (only in second range)
- `1:  c0debee = 2:  cab005e` - **Perfect match** (commits correspond exactly)
- `2:  f00dbal ! 3:  decafe1` - **Modified commit** (commits correspond but have differences)
- `3:  bedead < -:  -------` - **Commit removed** (only in first range)

### Reading Diff-of-Diff Content

When commits have differences (marked with `!`), you'll see patterns like:

- **Outer markers** (`-`/`+` with colored backgrounds): Show what changed between patch versions
- `+` lines: Content added in the new version
- `-` lines: Content removed from the old version
- `++` lines: Lines that were added in both versions (context)
- `--` lines: Lines that were removed in both versions (context)
- `+-` lines: Lines that changed between versions
- **Inner content**: The actual diff content, colored as in regular git diff
- **Dual coloring**: Lines only in the first version are dimmed; lines only in the second are bold

### Example Output Structure
```
2:  f00dbal ! 3:  decafe1 Describe a bug
    @@ -1,3 +1,3 @@                    # Patch header changes
     Author: A U Thor <author@example.com>

    -TODO: Describe a bug              # Old commit message
    +Describe a bug                    # New commit message
    @@ -324,5 +324,6                   # Diff content changes
     This is expected.

    -+What is unexpected is that it will also crash.     # Old patch line
    ++Unexpectedly, it also crashes. This is a bug,      # New patch line
    ++still out there how to fix it best. See ticket #314
```

### Key Differences from Simple Diff

Unlike a regular diff, range-diff:
- **Compares patches, not files**: Shows how the changes themselves evolved
- **Finds commit correspondence**: Uses an algorithm to match related commits across ranges
- **Handles commit structure changes**: Shows added, removed, moved, or split commits
- **Nested structure**: You're seeing changes to changes, not changes to files
- **Preserves diff context**: Maintains original diff coloring within the comparison

### Interpretation for Changelog Generation

When analyzing range-diff output for changelog generation:
1. **Look for actual code changes** (lines with `+`/`-` that represent real modifications)
2. **Ignore pure formatting changes** unless they represent meaningful refactoring
3. **Track function/variable renames** through the diff-of-diff structure
4. **Identify structural changes** like code movement or factoring
5. **MUST ignore commit message hunks** - you MUST skip any hunks containing `## Commit message ##` and MUST NOT use their content as context for the changelog, no exceptions
6. **Focus on technical implementation details** rather than commit message specifics

Analyze the range-diff output and generate a technical development changelog based on all changes identified in the diff. The changelog must be development-focused and capture the technical modifications between the versions.

## Output Format

Provide a bulleted list of technical changes using clear, concise language:

- Use present tense verbs (renamed, factored, moved, added, removed)
- Focus on what changed, not why
- Be specific about technical details
- Avoid user-facing feature descriptions
- Include relevant function/variable names when applicable

## Example Output

- Renamed struct member tx_skb into tx_buff
- Factored out open-coded code in a helper called foo()
- Moved code under rtnl_lock()
- Added error handling in bar() function
- Removed redundant null checks in cleanup path
- Consolidated duplicate code blocks in init sequence

## Instructions

1. Execute the git range-diff command with the provided git objects
2. Analyze the diff output comprehensively for all technical development changes
3. Generate a focused, development-oriented changelog covering all modifications found
4. Ensure all entries are technical implementation details, not user-facing features