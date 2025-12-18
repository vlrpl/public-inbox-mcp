The goal is to find if and what patches have been merged in a specific series. To achieve this, follow these steps:

1. **Find the thread**: Use the find_threads tool with a notmuch filter to locate the thread for your patch series.
   Use: '${notmuch_filter}' to find the thread

2. **Inspect the thread status**: Once you have the thread_id from the find_threads tool, use the show_thread() tool to retrieve detailed information about the thread, including all messages and their content.

3. **Verify merge status**: In the thread content, look for an email from patchwork-bot+netdevbpf that replies to the topmost email. This bot's emails contain information about the actions performed on the patch series. A merged or applied status will be explicitly mentioned in this reply.

4. **Fallback verification (REQUIRED for unmerged patches)**: For each patch in the series that does NOT show as merged from the patchwork-bot email, you MUST execute the following fallback verification:
   - Run the command: `git log --author='{author}' --oneline -n 1 --no-merges --grep '{subject}'`
   - Where `{author}` is the patch author (extracted from the patch's From header, not necessarily the email sender)
   - And `{subject}` is the email subject (the patch title)
   - This will search the git history for commits matching the author and subject, confirming if the patch was actually merged despite not being reported by patchwork-bot
   - **IMPORTANT**: Always execute this fallback for patches not confirmed as merged by patchwork-bot

5. **Output**: From the patchwork-bot+netdevbpf email (or from the fallback verification), extract the following information:
   - **Merged Patches**: The title and author of each patch that has been merged.
   - **Merged Status**: The status of the merge (e.g., "Merged," "Applied").
   - **Merged By**: The name of the person or system that performed the merge, if specified in the email.