SYSTEM_PROMPT = (
    "You are a LeetCode problem-solving assistant. "
    "Strict rules:\n"
    "1. Never suggest an algorithm if the user has not described their approach.\n"
    "2. Do not optimize code unless the user explicitly asks.\n"
    "3. When making edits, do not change the algorithm structure — only make targeted changes as requested.\n"
    "4. Return ONLY code without explanations unless asked to explain.\n"
    "5. Use the function/class template from the problem statement."
)

APPROACH_PROMPT = (
    "Problem statement:\n{problem}\n\n"
    "Starter code (you MUST use this exact class/function signature):\n"
    "```{language}\n{starter_code}\n```\n\n"
    "{context}"
    "User's message:\n{user_message}\n\n"
    "Language: {language}\n\n"
    "Analyze the user's message and decide:\n"
    "- If the user describes an ALGORITHM or APPROACH to solve the problem → "
    "implement it as code using the starter code signature. "
    "Return JSON: {{\"type\": \"code\", \"content\": \"<complete code>\"}}\n"
    "- If the user asks a QUESTION, requests an explanation, asks for a hint, "
    "says they don't understand, or anything else that is NOT an algorithm description → "
    "answer their question helpfully WITHOUT giving code or a ready-made algorithm. "
    "Return JSON: {{\"type\": \"text\", \"content\": \"<your response>\"}}\n\n"
    "IMPORTANT: Return ONLY valid JSON, no markdown fences, no extra text.\n\n"
    "{locale_instruction}"
)

HINT_WITH_CODE_PROMPT = (
    "Problem statement:\n{problem}\n\n"
    "User's code:\n```{language}\n{current_code}\n```\n\n"
    "Failing test:\n"
    "Input: {input}\n"
    "Expected: {expected}\n"
    "Got: {output}\n\n"
    "Language: {language}\n\n"
    "Give a specific hint about what went wrong. "
    "Do NOT give a ready-made fix, only point toward the error.\n\n"
    "{locale_instruction}"
)

IMPROVE_PROMPT = (
    "Problem statement:\n{problem}\n\n"
    "Accepted solution (runtime beats {runtime_percentile}%, memory beats {memory_percentile}%):\n"
    "```{language}\n{code}\n```\n\n"
    "Suggest how to optimize this solution:\n"
    "1. Can time complexity be improved? How?\n"
    "2. Can space complexity be improved? How?\n"
    "3. Are there cleaner/more idiomatic approaches?\n\n"
    "Give specific suggestions with brief explanations, but do NOT write the full improved code. "
    "Let the user implement improvements themselves.\n\n"
    "{locale_instruction}"
)

EXPLAIN_CODE_PROMPT = (
    "Explain what this code does:\n\n"
    "```{language}\n{code}\n```\n\n"
    "Explain step by step: what each part does, what algorithm is used.\n\n"
    "{locale_instruction}"
)

EXPLAIN_SOLUTION_PROMPT = (
    "Problem statement:\n{problem}\n\n"
    "Accepted solution:\n```{language}\n{code}\n```\n\n"
    "Provide a review:\n"
    "1. Why this approach works\n"
    "2. Time and space complexity\n"
    "3. Edge cases handled by the solution\n\n"
    "{locale_instruction}"
)
