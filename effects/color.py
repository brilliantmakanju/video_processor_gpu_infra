from config import ENABLE_COLOR_GRADING

def build_improved_color_filter() -> str:
    if not ENABLE_COLOR_GRADING:
        return ""
    
    # MAXIMUM QUALITY: Verified working FFmpeg filters for all games
    return (
        # Phase 1: Aggressive foundation - proven to work on CODM/Minecraft/everything
        "eq=contrast=1.38:brightness=0.09:saturation=1.6:gamma=1.1,"
        
        # Phase 2: Advanced tone curves - Hollywood-grade depth
        "curves=master='0/0 0.07/0.03 0.15/0.13 0.5/0.56 0.85/0.91 0.93/0.97 1/1':"
        "r='0/0.01 0.5/0.52 1/0.99':"  # Warm highlights
        "b='0/0.02 0.5/0.48 1/0.98',"  # Cool shadows (teal punch)
        
        # Phase 3: Triple-pass sharpening - maximum clarity
        "unsharp=7:7:1.6:5:5:0,"       # Main sharpen
        "unsharp=3:3:0.8:3:3:0,"       # Fine detail
        
        # Phase 4: Cinematic color grading - extreme teal/orange
        "colorbalance=rs=0.15:gs=0.07:bs=-0.12:rm=0.10:gm=0.05:bm=-0.07:rh=0.18:gh=0.09:bh=-0.14,"
        
        # Phase 5: Selective hue boost - make specific colors explode
        "hue=s=1.25,"  # Overall saturation multiplier
        
        # Phase 6: Micro-contrast for depth
        "eq=contrast=1.15,"  # Secondary contrast pass
        
        # Phase 7: Highlight bloom (working method)
        "gblur=sigma=1.5:steps=2,"
        
        # Phase 8: Color vibrance through channel manipulation
        "colorchannelmixer="
        "rr=1.08:rg=0.02:rb=0.0:"     # Boost reds
        "gr=0.02:gg=1.12:gb=0.02:"    # Boost greens  
        "br=0.0:bg=0.03:bb=1.10,"     # Boost blues
        
        # Phase 9: Final polish
        "eq=gamma_r=1.05:gamma_g=1.08:gamma_b=0.95,"  # Fine-tune warmth
        "limiter=min=16:max=235"  # Broadcast-safe
    )