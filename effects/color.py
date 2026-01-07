from config import ENABLE_COLOR_GRADING

def build_improved_color_filter() -> str:
    if not ENABLE_COLOR_GRADING:
        return ""
    
    # CLEAN CINEMATIC: Natural look with warm film-grade polish
    return (
        # Gentle foundation - barely noticeable but adds life
        "eq=contrast=1.12:brightness=0.02:saturation=1.15:gamma=1.02,"
        
        # Soft S-curve for natural depth (film look, not video game)
        "curves=master='0/0 0.15/0.12 0.5/0.51 0.85/0.88 1/1',"
        
        # Clean sharpening - detail without that "oversharpened" look
        "unsharp=5:5:0.5:3:3:0,"
        
        # Subtle warm cinematic grade - like sunset lighting
        "colorbalance=rs=0.02:gs=0.01:bs=-0.02:rm=0.02:gm=0.01:bm=-0.01:rh=0.03:gh=0.02:bh=-0.03,"
        
        # Gentle warmth in the image
        "eq=gamma_r=1.01:gamma_g=1.02:gamma_b=0.99,"
        
        # Safety limiter
        "limiter=min=16:max=235"
    )