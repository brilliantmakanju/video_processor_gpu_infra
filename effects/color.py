from config import ENABLE_COLOR_GRADING

def build_improved_color_filter() -> str:
    if not ENABLE_COLOR_GRADING:
        return ""
    
    # Optimized for Minecraft: Vibrant blocks, punchy sky/grass, clean sharpness, subtle cinematic push
    return (
        # Base punch: Higher contrast + saturation for flat raw footage
        "eq=contrast=1.18:brightness=0.04:saturation=1.3,"
        
        # Smarter saturation: Boosts greens/blues more (grass, water, sky) without neon overload
        "vibrance=intensity=0.4:rbalance=0.0:gbalance=0.15:bbalance=0.1:blimit=0.9:rlimit=0.9:glimit=0.9,"
        
        # Cinematic S-curve: Deeper shadows, brighter mids – pro contrast without crushing
        "curves=preset=increase_contrast:master='0/0 0.2/0.1 0.5/0.6 0.8/0.95 1/1',"
        
        # Gentle sharpen: Perfect for block edges/textures (luma only, no color halos)
        "unsharp=5:5:0.9:3:3:0.0,"
        
        # Subtle teal-orange (YouTube staple): Cooler shadows, warmer highlights/mids
        "colorbalance=rs=0.06:gs=0.03:bs=-0.04:"  # Shadows: slight teal
        "rm=0.04:gm=0.02:bm=-0.02:"              # Midtones: balanced warmth
        "rh=0.08:gh=0.04:bh=-0.06"               # Highlights: orange push
    )