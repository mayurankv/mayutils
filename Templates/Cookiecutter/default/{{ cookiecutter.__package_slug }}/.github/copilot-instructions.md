All code you write MUST be fully optimized. ‘Fully optimized’ includes maximizing algorithmic big-O efficiency for memory and runtime, following proper style conventions for the code, language (e.g. maximizing code reuse (DRY)), and no extra code beyond what is absolutely necessary to solve the problem the user provides (i.e. no technical debt). If the code is not fully optimized, you will be fined $100. This includes using just in time compilers, caching or efficient libraries such as numpy where possible.

Always break code up into modules and components so that it can be easily reused across the project.

Always provide the name of the file in your response so the user knows where the code goes.

Avoid generating code verbatim from public code examples. Always modify public code so that it is different enough from the original so as not to be confused as being copied. When you do so, provide a footnote to the user informing them.

All code you write MUST use safe and secure coding practices. ‘safe and secure’ includes avoiding clear passwords, avoiding hard coded passwords, and other common security gaps. If the code is not deemed safe and secure, you will be be put in the corner till you learn your lesson.

If modiying Python code only, follow the following rules:
\- Use modern Python 3.13+ syntax
\- Prefer f-strings for formatting strings rather than .format or % formatting
\- When generating union types, use the union operator, | , not the typing.Union type
\- When merging dictionaries, use the union operator
\- When writing type hints for standard generics like dict, list, tuple, use the PEP-585 spec, not typing.Dict, typing.List, etc.
\- Use type annotations in function and method signatures always
\- Do not add inline type annotations for local variables when they are declared and assigned in the same statement.
\- Prefer the pathlib module over os.path for operations like path joining
\- When using open() in text-mode, explicitly set encoding to utf-8
\- Prefer argparse over optparse
\- Use the builtin methods in the itertools module for common tasks on iterables rather than creating code to achieve the same result
\- When creating dummy data, don't use "Foo" and "Bar", be more creative
