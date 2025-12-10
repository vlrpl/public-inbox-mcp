# main.py
from fastmcp import FastMCP
import notmuch2
from email import message_from_file

next_rev_prompt = """
You are an expert Linux Kernel Maintainer and Code Review Assistant.
Your task is to process an email thread containing a software patch series and its review comments.
You must generate structured notes for each patch in the series.

To achieve this you MUST:

* Find the thread: Use the find_threads tool with a notmuch filter to locate the thread for your patch series.
  Use: '{notmuch_filter}' to find the thread
* Inspect the thread status: Once you have the thread_id from the find_threads tool, use the show_thread() tool to retrieve detailed information about the thread,
  including all messages and their content.

### 1. INPUT PROCESSING RULES

The input is a single email thread containing multiple messages (Root Patches and Replies),
separated by dashed lines (e.g., --------------------------------------------------).
Each message contains headers (Message ID, In-Reply-To, Subject, etc.) and a Body.

1.  **Thread Reconstruction:** Use Message ID and In-Reply-To headers to understand the conversation flow,
      but primarily use the Subject line to categorize feedback.
1.  **Group by Patch:** Distinct patches in the series are identified by their subject numbering (e.g., `[PATCH 1/6]`, `[PATCH 2/6]`).
      * You must group all replies (feedback) associated with "Patch 1" together.
      * You must group all replies associated with "Patch 2" together, and so on.
      * Cover letters (e.g. 0/6) usually do not require specific git notes unless there is broad architectural feedback not specific to a child patch.
2.  **Handle Nested Quotes:**
      * Emails use standard citation style (`>`, `>>`, `>>>`).
      * **Hunk detection:** The code or text being discussed is usually the quoted block (lines starting with `>`) immediately *preceding* a non-quoted line (the feedback).
      * **Reply detection:** A line *without* `>` is the new feedback (the "Reply").
      * Ignore lines that are purely polite filler (e.g., "Ack", "Thanks", "Reviewed-by" without context).

### 2. FILENAME GENERATION

For each specific patch found in the series, generate a filename using this logic:

1.  **Extract Number:** From the Subject `[PATCH v2 3/6] Description`, extract `003` (3 with two leading 00. If the number is 10/10, use 10 with one leading 0, 010).
2.  **Extract Description:** Extract the text after the prefix/number.
3.  **Format:** `./.notes/<NUMBER>_<SNAKE_CASE_DESCRIPTION>.txt`
      * *Example:* `[PATCH 1/6] Fix macb memory leak` -\> `./.notes/001_fix_macb_memory_leak.txt`

### 3. OUTPUT FORMAT

You must output a plain text stream.
One thread may result in multiple notes files (one per patch), so generate one file per patch.

Note that all the subsequent replies related to the same hunk must be squashed under the same existing diff and MUST report to what email/feedback they are referring to using `(Re: Feedback<FEEDBACK_NUMBER>)`.

Feedback1:
    [...]

Feedback2 (Re: Feedback1):
    [...]

Feedback3 (Re: Feedback2):
    [...]

See section 5 (EXAMPLE OUTPUT) for further details.

* You MUST never mangle the LITERAL_TEXT_OF_THE_COMMENT, do not remove spaces, nor \n.
  Keep it verbatim.
* Indent the whole feedback and Interpretation by 4 spaces, if multiline.
  Not just the first line.
* Never add trailing whitespaces for any reason.

Inside each file, verify every comment in the thread regarding that patch and format them as follows:

**ENTRY TEMPLATE:**
File: <DETECTED_FILENAME>
Hunk:

```diff
<THE_QUOTED_LINES_BEING_DISCUSSED>
```

Feedback1:
    Reviewer Name <reviewer@example.com> says:
    <LITERAL_TEXT_OF_THE_COMMENT>
Interpretation:
    <YOUR_EXPLANATION_OF_ACTION_REQUIRED>

-----

### 4. EXECUTION STEPS

1.  Scan the thread to identify all unique Patches (1/X, 2/X, etc.).
2.  For each Patch:
    a.  Generate the file as per section 2.
    b.  Find all replies in the thread containing `Re: ... <Patch Subject>`.
    c.  Scan the body of those replies.
    d.  Identify every distinct piece of feedback.
    e.  Locate the file path (look backwards in the email for `diff --git` or `+++`).
    f.  Output the structured output in the generate file regarding the patch currently processed.

### 5. EXAMPLE OUTPUT

File Content:

File: path/to/source_code.c

Hunk:

```diff

> + int example_function(int x) {
> +     return x + 1;
> + }
```

Feedback1:
    Reviewer Name <reviewer@example.com> says:
    Please add a comment explaining why we are incrementing by 1 here.
Interpretation:
    Reviewer Name is requesting documentation for the magic number in the return statement.

Feedback2 (Re: Feedback1):
    Author Name <author@example.com> says:
    Good point, I will define a constant for this.
Interpretation:
    The author agrees to refactor the code to use a named constant instead of a magic number.
"""

my_status_prompt = """
The goal is to find if and what patches have been merged in a specific series. To achieve this, follow these steps:

1. **Find the thread**: Use the find_threads tool with a notmuch filter to locate the thread for your patch series.
   Use: '{notmuch_filter}' to find the thread

2. **Inspect the thread status**: Once you have the thread_id from the find_threads tool, use the show_thread() tool to retrieve detailed information about the thread, including all messages and their content.

3. **Verify merge status**: In the thread content, look for an email from patchwork-bot+netdevbpf that replies to the topmost email. This bot's emails contain information about the actions performed on the patch series. A merged or applied status will be explicitly mentioned in this reply.

4. **Output**: From the patchwork-bot+netdevbpf email, extract the following information:
   - **Merged Patches**: The title and author of each patch that has been merged.
   - **Merged Status**: The status of the merge (e.g., "Merged," "Applied").
   - **Merged By**: The name of the person or system that performed the merge, if specified in the email.
"""

# Create an MCP server instance
mcp = FastMCP("Notmuch Server")

def walk_replies(messages, message):
    for reply in message.replies():
        messages.append(reply)
        walk_replies(messages, reply)

def retrieve_thread(thread_id: str) -> list[notmuch2.Message]:
    """
    Retrieve all messages in a thread given its thread ID.

    Args:
        thread_id (str): The thread ID to retrieve messages from

    Returns:
        list[notmuch2.Message]: A list of Message objects in the thread
    """
    messages = []

    try:
        # Open the notmuch database
        with notmuch2.Database(mode=notmuch2.Database.MODE.READ_ONLY) as db:
            # Search for the specific thread
            threads = db.threads(f"thread:{thread_id}")

            # Get the first (and should be only) thread
            thread = next(iter(threads), None)

            if thread:
                # Get all messages in the thread
                for message in thread.toplevel():
                    messages.append(message)
                    walk_replies(messages, message)
            else:
                print(f"Thread with ID {thread_id} not found")

    except Exception as e:
        print(f"Error: {e}")
        return []

    return messages

def get_email_body(msg) -> str:
    """
    Extract the body from an email.message.Message object.
    Handles plain text and multipart messages.
    """
    if msg.is_multipart():
        # Walk through the parts and find the first text/plain part
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = part.get("Content-Disposition", "")
            if content_type == "text/plain" and "attachment" not in content_disposition:
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="replace")
        # If no text/plain part found, fallback to first part's payload
        first_part = msg.get_payload(0)
        charset = first_part.get_content_charset() or "utf-8"
        return first_part.get_payload(decode=True).decode(charset, errors="replace")
    else:
        # Not multipart - just decode the payload
        charset = msg.get_content_charset() or "utf-8"
        return msg.get_payload(decode=True).decode(charset, errors="replace")


def get_message_info(message: notmuch2.Message) -> str:
    """
    Helper function to format basic information about a message as a string.

    Args:
        message (notmuch2.Message): The message object to format info for

    Returns:
        str: Formatted string containing message information
    """
    result = []
    result.append(f"Message ID: {message.messageid}")

    with message.path.open() as f:
        email_msg = message_from_file(f)

    result.append(f"In-Reply-To: {email_msg.get('In-Reply-To')}")
    result.append(f"From: {email_msg.get('From')}")
    result.append(f"To: {message.header('to')}")
    result.append(f"Subject: {email_msg.get('Subject')}")
    result.append(f"Date: {message.header('date')}")
    result.append(f"Tags: {', '.join(message.tags)}")

    body = get_email_body(email_msg)
    result.append("Body:")
    result.append(body)
    result.append("-" * 50)

    return '\n'.join(result)

def do_show_thread(tid: str) -> str:
    result = []

    messages = retrieve_thread(tid)
    for msg in messages:
        result.append(get_message_info(msg))

    return '\n'.join(result)

@mcp.tool()
def show_thread(thread_id: str) -> str:
    """
    Displays the content of a thread given its ID.

    Args:
        thread_id: The ID of the thread to display (without the prefix "thread:").

    Returns:
        A formatted string containing the messages in the thread,
        or an error message.
    """
    return do_show_thread(thread_id)

def do_find_threads(notmuch_filter: str) -> list[tuple[str, str]]:
    """
    Find patch series threads from a notmuch filter.

    Args:
        notmuch_filter: The notmuch query string to filter messages

    Returns:
        list[tuple[str, str]]: List of (thread_id, thread_subject) tuples for patch series

    Raises:
        ValueError: If notmuch_filter is empty or None
        RuntimeError: If database access fails
    """
    if not notmuch_filter or not notmuch_filter.strip():
        raise ValueError("notmuch_filter cannot be empty or None")

    series_threads = []
    seen_threads = set()

    try:
        with notmuch2.Database(mode=notmuch2.Database.MODE.READ_ONLY) as db:
            messages = db.messages(notmuch_filter)

            for message in messages:
                thread_id = message.threadid

                # Skip if we've already processed this thread
                if thread_id in seen_threads:
                    continue

                subject = message.header('subject') or ""

                # Check if this is a patch email (not a reply)
                is_patch = "PATCH" in subject.upper()
                is_reply = any(subject.upper().startswith(prefix) for prefix in ["RE:", "R:"])

                if is_patch and not is_reply:
                    # Get thread subject directly from the thread
                    thread_query = db.threads(f"thread:{thread_id}")
                    try:
                        thread = next(iter(thread_query))
                        series_threads.append((thread_id, thread.subject or subject))
                        seen_threads.add(thread_id)
                    except StopIteration:
                        # Thread not found, use message subject as fallback
                        series_threads.append((thread_id, subject))
                        seen_threads.add(thread_id)

    except notmuch2.NotmuchError as e:
        raise RuntimeError(f"Notmuch database error: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error while searching threads: {e}")

    return series_threads

@mcp.tool()
def find_threads(notmuch_filter: str) -> list[tuple[str, str]]:
    """
    Finds series using a notmuch filter string and returns a list containing the pair
    (thread id, thread subject) corresponding to each thread matching the filter.
    notmuch_filter must match only toplevel messages or messages whose subject
    contains "PATCH" and are no "Re:" "RE:" "R:"

    Args:
        notmuch_filter: The notmuch query to execute.
                       Example: "from:jane@example.com AND tag:unread"

    Returns:
        list[(str, str)]: A list of thread IDs and subjects for each thread matching the search criteria
    """
    return do_find_threads(notmuch_filter)

@mcp.prompt
def my_status(notmuch_filter: str) -> str:
    """Show the status of the patches pushed on a mailing list"""
    return my_status_prompt

@mcp.prompt
def next_revision(notmuch_filter: str) -> str:
    """Creates the git notes for the next respin of the series"""
    return next_rev_prompt

if __name__ == "__main__":
    import sys

    # To run this server:
    # 1. Make sure you have notmuch installed and configured.
    # 2. Install the required Python libraries:
    #    pip install fastmcp python-notmuch2
    # 3. Run the server from your terminal:
    #    fastmcp run main.py

    if len(sys.argv) == 2 and sys.argv[1] == "stdio":
        mcp.run()
    if len(sys.argv) == 2:
        threads = do_find_threads(sys.argv[1])
        do_show_thread(threads[0][0])
    else:
        mcp.run(transport="http", host="0.0.0.0", port=8000, path="/")
