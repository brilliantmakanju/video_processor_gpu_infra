def escape_filter_text(text: str) -> str:
    """Escape text for FFmpeg filters."""
    text = text.replace('\\', '\\\\')
    text = text.replace("'", "'\\\\\\''")
    text = text.replace(':', '\\:')
    text = text.replace('[', '\\[')
    text = text.replace(']', '\\]')
    return text
