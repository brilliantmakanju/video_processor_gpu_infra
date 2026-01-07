from config import ENABLE_COLOR_GRADING

def build_improved_color_filter() -> str:
    if not ENABLE_COLOR_GRADING:
        return ""
    
    # SOFT CINEMATIC: Gentle, smooth, calming film aesthetic
    return (
        # Very gentle foundation - barely there
        "eq=contrast=1.08:brightness=0.02:saturation=1.10:gamma=1.02,"
        
        # Soft S-curve - just adds a bit of depth
        "curves=master='0/0.01 0.25/0.24 0.5/0.51 0.75/0.76 1/1',"
        
        # Lift shadows for soft, open look
        "curves=master='0/0.04 0.15/0.14 1/1',"
        
        # Very light sharpening - clarity without edge
        "unsharp=5:5:0.3:3:3:0,"
        
        # Subtle warm tones - barely noticeable
        "colorbalance=rs=0.01:gs=0.01:bs=-0.01:rm=0.01:gm=0.01:bm=-0.01:rh=0.02:gh=0.01:bh=-0.02,"
        
        # Gentle warmth
        "eq=gamma_r=1.01:gamma_g=1.01:gamma_b=0.99,"
        
        # Smooth everything out
        "hqdn3d=0.8:0.8:1.5:1.5,"
        
        # Safety
        "limiter=min=16:max=235"
    )