# One-off script: give chats created before Stage 4 a real title.
# Run it once with:  python fix_titles.py
# It's safe to run again: it only touches chats still called "New chat".

import db

fixed = 0
for conversation in db.list_conversations():
    if conversation["title"] != "New chat":
        continue  # already has a real title

    # Find the first message the user sent in this chat
    messages = db.get_messages(conversation["id"])
    first_user_message = next((m["content"] for m in messages if m["role"] == "user"), None)

    if first_user_message is None:
        continue  # empty chat: leave it as "New chat"

    title = db.make_title(first_user_message)
    db.set_title(conversation["id"], title)
    print(f"Chat {conversation['id']}: {title}")
    fixed += 1

print(f"Done. Renamed {fixed} chat(s).")
