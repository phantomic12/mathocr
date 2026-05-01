"""Post-process and normalize LaTeX output from LLM."""
import re


def clean_latex(raw: str) -> str:
    """Normalize and clean LLM-generated LaTeX."""
    if not raw:
        return ""

    # Strip markdown code fences
    text = re.sub(r"```(?:latex)?\s*", "", raw)
    text = re.sub(r"```\s*$", "", text)

    # Remove trailing "Explanation:" blocks
    text = re.sub(r"\n*Explanation:.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\n*Reasoning:.*", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Strip inline comments
    text = re.sub(r"%[^\n]*", "", text)

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text


def extract_latex_blocks(text: str) -> list[str]:
    """Extract display-math blocks from raw text."""
    pattern = r"\$\$([^$]+)\$\$|\$([^$\n]+)\$|\\\[(.*?)\\\]|\\\((.+?)\\\)"
    return [m.group(1) or m.group(2) or m.group(3) or m.group(4) or ""
            for m in re.finditer(pattern, text, re.DOTALL)]
