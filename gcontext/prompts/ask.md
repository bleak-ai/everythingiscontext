---
description: Load this agent's context and answer a question using its state
parameters:
  - name: question
    description: What you want to know or do (e.g. "what is the current storage capacity of coolify")
    required: false
---
The user is asking this agent a question. Use the gcontext tools (read_file,
list_dir, grep) to find the answer in the agent's state folder.

The question: "$question"

## How to answer

1. Start by reading agent.md if you have not already.
2. Use list_dir on connections/, modules/, and agents/ to see what is available.
3. Search the relevant modules, connections, and agents for the answer using grep
   and read_file.
4. Answer concisely based on what you find. If the state folder does not
   contain enough information, say so and suggest what the user could add.
5. If the question is empty, introduce yourself: say what you are, what
   modules, connections, and agents you have, and what you can help with.
