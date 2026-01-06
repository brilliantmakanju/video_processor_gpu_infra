from config import ENABLE_COLOR_GRADING

def build_improved_color_filter() -> str:
    """
    High-quality color enhancement for YouTube.
    Includes:
    - eq: brightness, contrast, saturation
    - unsharp: sharpness enhancement
    - vibrance: color vibrance
    """
    if not ENABLE_COLOR_GRADING:
        return ""
    
    # eq: brightness=0.02, contrast=1.1, saturation=1.15
    # unsharp: 3:3:1.5:3:3:0.5 (luma_msize_x:luma_msize_y:luma_amount:chroma_msize_x:chroma_msize_y:chroma_amount)
    # vibrance: intensity=0.15
    return "eq=brightness=0.02:contrast=1.1:saturation=1.15,unsharp=3:3:1.5:3:3:0.5,vibrance=0.15"
