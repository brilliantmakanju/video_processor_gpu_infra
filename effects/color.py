from config import ENABLE_COLOR_GRADING

def build_improved_color_filter() -> str:
    if not ENABLE_COLOR_GRADING:
        return ""
    
    # ULTIMATE PRO VISUALS: Cinema-grade color science for elite gaming content
    return (
        # Phase 1: Foundation - Fix flat capture & boost dynamic range
        "eq=contrast=1.35:brightness=0.08:saturation=1.55:gamma=1.05,"
        
        # Phase 2: Intelligent color explosion - Vibrance + selective saturation
        "vibrance=intensity=0.65:rbal=1.15:gbal=1.3:bbal=1.2,"
        
        # Phase 3: Advanced tone mapping - Dual S-curve for Hollywood depth
        "curves=master='0/0 0.05/0.02 0.15/0.12 0.5/0.58 0.85/0.92 0.95/0.98 1/1':"
        "red='0/0.02 0.5/0.52 1/0.98':"      # Warm highlights
        "blue='0/0 0.5/0.48 1/1',"           # Cool shadows (teal pop)
        
        # Phase 4: Multi-pass sharpening - Clarity without artifacts
        "cas=0.7,"  # AMD FidelityFX CAS - ultra-clean adaptive sharpen
        "unsharp=7:7:1.5:5:5:0.0,"  # Detail enhancement
        
        # Phase 5: Cinematic color grading - Blockbuster teal/orange
        "colorbalance="
        "rs=0.12:gs=0.06:bs=-0.10:"   # Shadows: deep teal/cyan
        "rm=0.08:gm=0.04:bm=-0.05:"   # Midtones: warm punch
        "rh=0.15:gh=0.08:bh=-0.12,"   # Highlights: orange glow
        
        # Phase 6: Selective color boost - Make key colors POP
        "selectivecolor="
        "reds=0.15:0:0:0:"        # Boost red intensity (health bars, fire)
        "cyans=0:0.12:-0.08:0:"   # Enhance cyan/teal (UI, water)
        "yellows=0.10:0:-0.08:0," # Punch yellows (explosions, loot)
        
        # Phase 7: Film-grade finish - Subtle halation & glow
        "gblur=sigma=0.5:steps=2,"  # Micro bloom on highlights
        "mix=inputs=2:weights='1 0.08'[tmp];[tmp]"  # Blend 8% glow
        "hqdn3d=1.5:1.5:3:3,"  # Light denoise for clean look
        
        # Phase 8: Final polish - Edge contrast & micro-detail
        "smartblur=lr=0.5:ls=-0.5:cr=0.5:cs=-0.5,"  # Edge enhancement
        "atadenoise=0a=0.02:0b=0.03,"  # Temporal stability for smooth playback
        "limiter=min=16:max=235"  # Broadcast-safe levels (prevents clipping)
    )