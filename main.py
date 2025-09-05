# main.py
from fastmcp import FastMCP
import notmuch2
from email import message_from_file

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

    result.append(f"From: {email_msg.get('From')}")
    result.append(f"To: {message.header('to')}")
    result.append(f"Subject: {email_msg.get('Subject')}")
    result.append(f"Date: {message.header('date')}")
    result.append(f"Message-id: {message.messageid}")
    result.append(f"Tags: {', '.join(message.tags)}")

    body = get_email_body(email_msg)
    result.append("Body:")
    result.append(body)
    result.append("-" * 50)

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
    result = []

    messages = retrieve_thread(thread_id)
    for msg in messages:
        result.append(get_message_info(msg))

    return '\n'.join(result)

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

    # print(series_threads)
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
        do_find_threads(sys.argv[1])
    else:
        mcp.run(transport="http", host="0.0.0.0", port=8000, path="/")
