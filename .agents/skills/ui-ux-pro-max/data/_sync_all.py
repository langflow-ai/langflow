#!/usr/bin/env python3
"""
Sync colors.csv and ui-reasoning.csv with the updated products.csv (161 entries).
- Remove deleted product types
- Rename mismatched entries
- Add new entries for missing product types
- Keep colors.csv aligned 1:1 with products.csv
- Renumber everything
"""
import csv, os, json

BASE = os.path.dirname(os.path.abspath(__file__))

# ─── Color derivation helpers ────────────────────────────────────────────────
def h2r(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def r2h(r, g, b):
    return f"#{max(0,min(255,int(r))):02X}{max(0,min(255,int(g))):02X}{max(0,min(255,int(b))):02X}"

def lum(h):
    r, g, b = [x/255.0 for x in h2r(h)]
    r, g, b = [(x/12.92 if x<=0.03928 else ((x+0.055)/1.055)**2.4) for x in (r, g, b)]
    return 0.2126*r + 0.7152*g + 0.0722*b

def is_dark(bg):
    return lum(bg) < 0.18

def on_color(bg):
    return "#FFFFFF" if lum(bg) < 0.4 else "#0F172A"

def blend(a, b, f=0.15):
    ra, ga, ba = h2r(a)
    rb, gb, bb = h2r(b)
    return r2h(ra+(rb-ra)*f, ga+(gb-ga)*f, ba+(bb-ba)*f)

def shift(h, n):
    r, g, b = h2r(h)
    return r2h(r+n, g+n, b+n)

def derive_row(pt, pri, sec, acc, bg, notes=""):
    """Generate full 16-token color row from 4 base colors."""
    dark = is_dark(bg)
    fg = "#FFFFFF" if dark else "#0F172A"
    on_pri = on_color(pri)
    on_sec = on_color(sec)
    on_acc = on_color(acc)
    card = shift(bg, 10) if dark else "#FFFFFF"
    card_fg = "#FFFFFF" if dark else "#0F172A"
    muted = blend(bg, pri, 0.08) if dark else blend("#FFFFFF", pri, 0.06)
    muted_fg = "#94A3B8" if dark else "#64748B"
    border = f"rgba(255,255,255,0.08)" if dark else blend("#FFFFFF", pri, 0.12)
    destr = "#DC2626"
    on_destr = "#FFFFFF"
    ring = pri
    return [pt, pri, on_pri, sec, on_sec, acc, on_acc, bg, fg, card, card_fg, muted, muted_fg, border, destr, on_destr, ring, notes]

# ─── Rename maps ─────────────────────────────────────────────────────────────
COLOR_RENAMES = {
    "Quantum Computing": "Quantum Computing Interface",
    "Biohacking / Longevity": "Biohacking / Longevity App",
    "Autonomous Systems": "Autonomous Drone Fleet Manager",
    "Generative AI Art": "Generative Art Platform",
    "Spatial / Vision OS": "Spatial Computing OS / App",
    "Climate Tech": "Sustainable Energy / Climate Tech",
}
UI_RENAMES = {
    "Architecture/Interior": "Architecture / Interior",
    "Autonomous Drone Fleet": "Autonomous Drone Fleet Manager",
    "B2B SaaS Enterprise": "B2B Service",
    "Biohacking/Longevity App": "Biohacking / Longevity App",
    "Biotech/Life Sciences": "Biotech / Life Sciences",
    "Developer Tool/IDE": "Developer Tool / IDE",
    "Education": "Educational App",
    "Fintech (Banking)": "Fintech/Crypto",
    "Government/Public": "Government/Public Service",
    "Home Services": "Home Services (Plumber/Electrician)",
    "Micro-Credentials/Badges": "Micro-Credentials/Badges Platform",
    "Music/Entertainment": "Music Streaming",
    "Quantum Computing": "Quantum Computing Interface",
    "Real Estate": "Real Estate/Property",
    "Remote Work/Collaboration": "Remote Work/Collaboration Tool",
    "Restaurant/Food": "Restaurant/Food Service",
    "SaaS Dashboard": "Analytics Dashboard",
    "Space Tech/Aerospace": "Space Tech / Aerospace",
    "Spatial Computing OS": "Spatial Computing OS / App",
    "Startup Landing": "Micro SaaS",
    "Sustainable Energy/Climate": "Sustainable Energy / Climate Tech",
    "Travel/Tourism": "Travel/Tourism Agency",
    "Wellness/Mental Health": "Mental Health App",
}

REMOVE_TYPES = {
    "Service Landing Page", "Sustainability/ESG Platform",
    "Cleaning Service", "Coffee Shop",
    "Consulting Firm", "Conference/Webinar Platform",
}

# ─── New color definitions: (primary, secondary, accent, bg, notes) ──────────
# Grouped by category for clarity. Each tuple generates a full 16-token row.
NEW_COLORS = {
    # ── Old #97-#116 that never got colors ──
    "Todo & Task Manager":         ("#2563EB","#3B82F6","#059669","#F8FAFC","Functional blue + progress green"),
    "Personal Finance Tracker":    ("#1E40AF","#3B82F6","#059669","#0F172A","Trust blue + profit green on dark"),
    "Chat & Messaging App":        ("#2563EB","#6366F1","#059669","#FFFFFF","Messenger blue + online green"),
    "Notes & Writing App":         ("#78716C","#A8A29E","#D97706","#FFFBEB","Warm ink + amber accent on cream"),
    "Habit Tracker":               ("#D97706","#F59E0B","#059669","#FFFBEB","Streak amber + habit green"),
    "Food Delivery / On-Demand":   ("#EA580C","#F97316","#2563EB","#FFF7ED","Appetizing orange + trust blue"),
    "Ride Hailing / Transportation":("#1E293B","#334155","#2563EB","#0F172A","Map dark + route blue"),
    "Recipe & Cooking App":        ("#9A3412","#C2410C","#059669","#FFFBEB","Warm terracotta + fresh green"),
    "Meditation & Mindfulness":    ("#7C3AED","#8B5CF6","#059669","#FAF5FF","Calm lavender + mindful green"),
    "Weather App":                 ("#0284C7","#0EA5E9","#F59E0B","#F0F9FF","Sky blue + sun amber"),
    "Diary & Journal App":         ("#92400E","#A16207","#6366F1","#FFFBEB","Warm journal brown + ink violet"),
    "CRM & Client Management":     ("#2563EB","#3B82F6","#059669","#F8FAFC","Professional blue + deal green"),
    "Inventory & Stock Management":("#334155","#475569","#059669","#F8FAFC","Industrial slate + stock green"),
    "Flashcard & Study Tool":      ("#7C3AED","#8B5CF6","#059669","#FAF5FF","Study purple + correct green"),
    "Booking & Appointment App":   ("#0284C7","#0EA5E9","#059669","#F0F9FF","Calendar blue + available green"),
    "Invoice & Billing Tool":      ("#1E3A5F","#2563EB","#059669","#F8FAFC","Navy professional + paid green"),
    "Grocery & Shopping List":     ("#059669","#10B981","#D97706","#ECFDF5","Fresh green + food amber"),
    "Timer & Pomodoro":            ("#DC2626","#EF4444","#059669","#0F172A","Focus red on dark + break green"),
    "Parenting & Baby Tracker":    ("#EC4899","#F472B6","#0284C7","#FDF2F8","Soft pink + trust blue"),
    "Scanner & Document Manager":  ("#1E293B","#334155","#2563EB","#F8FAFC","Document grey + scan blue"),
    # ── A. Utility / Productivity ──
    "Calendar & Scheduling App":   ("#2563EB","#3B82F6","#059669","#F8FAFC","Calendar blue + event green"),
    "Password Manager":            ("#1E3A5F","#334155","#059669","#0F172A","Vault dark blue + secure green"),
    "Expense Splitter / Bill Split":("#059669","#10B981","#DC2626","#F8FAFC","Balance green + owe red"),
    "Voice Recorder & Memo":       ("#DC2626","#EF4444","#2563EB","#FFFFFF","Recording red + waveform blue"),
    "Bookmark & Read-Later":       ("#D97706","#F59E0B","#2563EB","#FFFBEB","Warm amber + link blue"),
    "Translator App":              ("#2563EB","#0891B2","#EA580C","#F8FAFC","Global blue + teal + accent orange"),
    "Calculator & Unit Converter": ("#EA580C","#F97316","#2563EB","#1C1917","Operation orange on dark"),
    "Alarm & World Clock":         ("#D97706","#F59E0B","#6366F1","#0F172A","Time amber + night indigo on dark"),
    "File Manager & Transfer":     ("#2563EB","#3B82F6","#D97706","#F8FAFC","Folder blue + file amber"),
    "Email Client":                ("#2563EB","#3B82F6","#DC2626","#FFFFFF","Inbox blue + priority red"),
    # ── B. Games ──
    "Casual Puzzle Game":          ("#EC4899","#8B5CF6","#F59E0B","#FDF2F8","Cheerful pink + reward gold"),
    "Trivia & Quiz Game":          ("#2563EB","#7C3AED","#F59E0B","#EFF6FF","Quiz blue + gold leaderboard"),
    "Card & Board Game":           ("#15803D","#166534","#D97706","#0F172A","Felt green + gold on dark"),
    "Idle & Clicker Game":         ("#D97706","#F59E0B","#7C3AED","#FFFBEB","Coin gold + prestige purple"),
    "Word & Crossword Game":       ("#15803D","#059669","#D97706","#FFFFFF","Word green + letter amber"),
    "Arcade & Retro Game":         ("#DC2626","#2563EB","#22C55E","#0F172A","Neon red+blue on dark + score green"),
    # ── C. Creator Tools ──
    "Photo Editor & Filters":      ("#7C3AED","#6366F1","#0891B2","#0F172A","Editor violet + filter cyan on dark"),
    "Short Video Editor":          ("#EC4899","#DB2777","#2563EB","#0F172A","Video pink on dark + timeline blue"),
    "Drawing & Sketching Canvas":  ("#7C3AED","#8B5CF6","#0891B2","#1C1917","Canvas purple + tool teal on dark"),
    "Music Creation & Beat Maker": ("#7C3AED","#6366F1","#22C55E","#0F172A","Studio purple + waveform green on dark"),
    "Meme & Sticker Maker":        ("#EC4899","#F59E0B","#2563EB","#FFFFFF","Viral pink + comedy yellow + share blue"),
    "AI Photo & Avatar Generator": ("#7C3AED","#6366F1","#EC4899","#FAF5FF","AI purple + generation pink"),
    "Link-in-Bio Page Builder":    ("#2563EB","#7C3AED","#EC4899","#FFFFFF","Brand blue + creator purple"),
    # ── D. Personal Life ──
    "Wardrobe & Outfit Planner":   ("#BE185D","#EC4899","#D97706","#FDF2F8","Fashion rose + gold accent"),
    "Plant Care Tracker":          ("#15803D","#059669","#D97706","#F0FDF4","Nature green + sun yellow"),
    "Book & Reading Tracker":      ("#78716C","#92400E","#D97706","#FFFBEB","Book brown + page amber"),
    "Couple & Relationship App":   ("#BE185D","#EC4899","#DC2626","#FDF2F8","Romance rose + love red"),
    "Family Calendar & Chores":    ("#2563EB","#059669","#D97706","#F8FAFC","Family blue + chore green"),
    "Mood Tracker":                ("#7C3AED","#6366F1","#D97706","#FAF5FF","Mood purple + insight amber"),
    "Gift & Wishlist":             ("#DC2626","#D97706","#EC4899","#FFF1F2","Gift red + gold + surprise pink"),
    # ── E. Health ──
    "Running & Cycling GPS":       ("#EA580C","#F97316","#059669","#0F172A","Energetic orange + pace green on dark"),
    "Yoga & Stretching Guide":     ("#6B7280","#78716C","#0891B2","#F5F5F0","Sage neutral + calm teal"),
    "Sleep Tracker":               ("#4338CA","#6366F1","#7C3AED","#0F172A","Night indigo + dream violet on dark"),
    "Calorie & Nutrition Counter": ("#059669","#10B981","#EA580C","#ECFDF5","Healthy green + macro orange"),
    "Period & Cycle Tracker":      ("#BE185D","#EC4899","#7C3AED","#FDF2F8","Blush rose + fertility lavender"),
    "Medication & Pill Reminder":  ("#0284C7","#0891B2","#DC2626","#F0F9FF","Medical blue + alert red"),
    "Water & Hydration Reminder":  ("#0284C7","#06B6D4","#0891B2","#F0F9FF","Refreshing blue + water cyan"),
    "Fasting & Intermittent Timer":("#6366F1","#4338CA","#059669","#0F172A","Fasting indigo on dark + eating green"),
    # ── F. Social ──
    "Anonymous Community / Confession":("#475569","#334155","#0891B2","#0F172A","Protective grey + subtle teal on dark"),
    "Local Events & Discovery":    ("#EA580C","#F97316","#2563EB","#FFF7ED","Event orange + map blue"),
    "Study Together / Virtual Coworking":("#2563EB","#3B82F6","#059669","#F8FAFC","Focus blue + session green"),
    # ── G. Education ──
    "Coding Challenge & Practice": ("#22C55E","#059669","#D97706","#0F172A","Code green + difficulty amber on dark"),
    "Kids Learning (ABC & Math)":  ("#2563EB","#F59E0B","#EC4899","#EFF6FF","Learning blue + play yellow + fun pink"),
    "Music Instrument Learning":   ("#DC2626","#9A3412","#D97706","#FFFBEB","Musical red + warm amber"),
    # ── H. Transport ──
    "Parking Finder":              ("#2563EB","#059669","#DC2626","#F0F9FF","Available blue/green + occupied red"),
    "Public Transit Guide":        ("#2563EB","#0891B2","#EA580C","#F8FAFC","Transit blue + line colors"),
    "Road Trip Planner":           ("#EA580C","#0891B2","#D97706","#FFF7ED","Adventure orange + map teal"),
    # ── I. Safety & Lifestyle ──
    "VPN & Privacy Tool":          ("#1E3A5F","#334155","#22C55E","#0F172A","Shield dark + connected green"),
    "Emergency SOS & Safety":      ("#DC2626","#EF4444","#2563EB","#FFF1F2","Alert red + safety blue"),
    "Wallpaper & Theme App":       ("#7C3AED","#EC4899","#2563EB","#FAF5FF","Aesthetic purple + trending pink"),
    "White Noise & Ambient Sound": ("#475569","#334155","#4338CA","#0F172A","Ambient grey + deep indigo on dark"),
    "Home Decoration & Interior Design":("#78716C","#A8A29E","#D97706","#FAF5F2","Interior warm grey + gold accent"),
}

# ─── 1. REBUILD colors.csv ───────────────────────────────────────────────────
def rebuild_colors():
    src = os.path.join(BASE, "colors.csv")
    with open(src, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        existing = list(reader)

    # Build lookup: Product Type -> row data
    color_map = {}
    for row in existing:
        pt = row.get("Product Type", "").strip()
        if not pt:
            continue
        # Remove deleted types
        if pt in REMOVE_TYPES:
            print(f"  [colors] REMOVE: {pt}")
            continue
        # Rename mismatched types
        if pt in COLOR_RENAMES:
            new_name = COLOR_RENAMES[pt]
            print(f"  [colors] RENAME: {pt} → {new_name}")
            row["Product Type"] = new_name
            pt = new_name
        color_map[pt] = row

    # Read products.csv to get the correct order
    with open(os.path.join(BASE, "products.csv"), newline="", encoding="utf-8") as f:
        products = list(csv.DictReader(f))

    # Build final rows in products.csv order
    final_rows = []
    added = 0
    for i, prod in enumerate(products, 1):
        pt = prod["Product Type"]
        if pt in color_map:
            row = color_map[pt]
            row["No"] = str(i)
            final_rows.append(row)
        elif pt in NEW_COLORS:
            pri, sec, acc, bg, notes = NEW_COLORS[pt]
            new_row = derive_row(pt, pri, sec, acc, bg, notes)
            d = dict(zip(headers, [str(i)] + new_row))
            final_rows.append(d)
            added += 1
        else:
            print(f"  [colors] WARNING: No color data for '{pt}' - using defaults")
            new_row = derive_row(pt, "#2563EB", "#3B82F6", "#059669", "#F8FAFC", "Auto-generated default")
            d = dict(zip(headers, [str(i)] + new_row))
            final_rows.append(d)
            added += 1

    # Write
    with open(src, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(final_rows)

    product_count = len(products)
    print(f"\n  ✅ colors.csv: {len(final_rows)} rows ({product_count} products)")
    print(f"     Added: {added} new color rows")

# ─── 2. REBUILD ui-reasoning.csv ─────────────────────────────────────────────
def derive_ui_reasoning(prod):
    """Generate ui-reasoning row from products.csv row."""
    pt = prod["Product Type"]
    style = prod.get("Primary Style Recommendation", "")
    landing = prod.get("Landing Page Pattern", "")
    color_focus = prod.get("Color Palette Focus", "")
    considerations = prod.get("Key Considerations", "")
    keywords = prod.get("Keywords", "")

    # Typography mood derived from style
    typo_map = {
        "Minimalism": "Professional + Clean hierarchy",
        "Glassmorphism": "Modern + Clear hierarchy",
        "Brutalism": "Bold + Oversized + Monospace",
        "Claymorphism": "Playful + Rounded + Friendly",
        "Dark Mode": "High contrast + Light on dark",
        "Neumorphism": "Subtle + Soft + Monochromatic",
        "Flat Design": "Bold + Clean + Sans-serif",
        "Vibrant": "Energetic + Bold + Large",
        "Aurora": "Elegant + Gradient-friendly",
        "AI-Native": "Conversational + Minimal chrome",
        "Organic": "Warm + Humanist + Natural",
        "Motion": "Dynamic + Hierarchy-shifting",
        "Accessible": "Large + High contrast + Clear",
        "Soft UI": "Modern + Accessible + Balanced",
        "Trust": "Professional + Serif accents",
        "Swiss": "Grid-based + Mathematical + Helvetica",
        "3D": "Immersive + Spatial + Variable",
        "Retro": "Nostalgic + Monospace + Neon",
        "Cyberpunk": "Terminal + Monospace + Neon",
        "Pixel": "Retro + Blocky + 8-bit",
    }
    typo_mood = "Professional + Clear hierarchy"
    for key, val in typo_map.items():
        if key.lower() in style.lower():
            typo_mood = val
            break

    # Key effects from style
    eff_map = {
        "Glassmorphism": "Backdrop blur (10-20px) + Translucent overlays",
        "Neumorphism": "Dual shadows (light+dark) + Soft press 150ms",
        "Claymorphism": "Multi-layer shadows + Spring bounce + Soft press 200ms",
        "Brutalism": "No transitions + Hard borders + Instant feedback",
        "Dark Mode": "Subtle glow + Neon accents + High contrast",
        "Flat Design": "Color shift hover + Fast 150ms transitions + No shadows",
        "Minimalism": "Subtle hover 200ms + Smooth transitions + Clean",
        "Motion-Driven": "Scroll animations + Parallax + Page transitions",
        "Micro-interactions": "Haptic feedback + Small 50-100ms animations",
        "Vibrant": "Large section gaps 48px+ + Color shift hover + Scroll-snap",
        "Aurora": "Flowing gradients 8-12s + Color morphing",
        "AI-Native": "Typing indicator + Streaming text + Context reveal",
        "Organic": "Rounded 16-24px + Natural shadows + Flowing SVG",
        "Soft UI": "Improved shadows + Modern 200-300ms + Focus visible",
        "3D": "WebGL/Three.js + Parallax 3-5 layers + Physics 300-400ms",
        "Trust": "Clear focus rings + Badge hover + Metric pulse",
        "Accessible": "Focus rings 3-4px + ARIA + Reduced motion",
    }
    key_effects = "Subtle hover (200ms) + Smooth transitions"
    for key, val in eff_map.items():
        if key.lower() in style.lower():
            key_effects = val
            break

    # Decision rules
    rules = {}
    if "dark" in style.lower() or "oled" in style.lower():
        rules["if_light_mode_needed"] = "provide-theme-toggle"
    if "glass" in style.lower():
        rules["if_low_performance"] = "fallback-to-flat"
    if "conversion" in landing.lower():
        rules["if_conversion_focused"] = "add-urgency-colors"
    if "social" in landing.lower():
        rules["if_trust_needed"] = "add-testimonials"
    if "data" in keywords.lower() or "dashboard" in keywords.lower():
        rules["if_data_heavy"] = "prioritize-data-density"
    if not rules:
        rules["if_ux_focused"] = "prioritize-clarity"
        rules["if_mobile"] = "optimize-touch-targets"

    # Anti-patterns
    anti_patterns = []
    if "minimalism" in style.lower() or "minimal" in style.lower():
        anti_patterns.append("Excessive decoration")
    if "dark" in style.lower():
        anti_patterns.append("Pure white backgrounds")
    if "flat" in style.lower():
        anti_patterns.append("Complex shadows + 3D effects")
    if "vibrant" in style.lower():
        anti_patterns.append("Muted colors + Low energy")
    if "accessible" in style.lower():
        anti_patterns.append("Color-only indicators")
    if not anti_patterns:
        anti_patterns = ["Inconsistent styling", "Poor contrast ratios"]
    anti_str = " + ".join(anti_patterns[:2])

    return {
        "UI_Category": pt,
        "Recommended_Pattern": landing,
        "Style_Priority": style,
        "Color_Mood": color_focus,
        "Typography_Mood": typo_mood,
        "Key_Effects": key_effects,
        "Decision_Rules": json.dumps(rules),
        "Anti_Patterns": anti_str,
        "Severity": "HIGH"
    }


def rebuild_ui_reasoning():
    src = os.path.join(BASE, "ui-reasoning.csv")
    with open(src, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        existing = list(reader)

    # Build lookup
    ui_map = {}
    for row in existing:
        cat = row.get("UI_Category", "").strip()
        if not cat:
            continue
        if cat in REMOVE_TYPES:
            print(f"  [ui-reason] REMOVE: {cat}")
            continue
        if cat in UI_RENAMES:
            new_name = UI_RENAMES[cat]
            print(f"  [ui-reason] RENAME: {cat} → {new_name}")
            row["UI_Category"] = new_name
            cat = new_name
        ui_map[cat] = row

    with open(os.path.join(BASE, "products.csv"), newline="", encoding="utf-8") as f:
        products = list(csv.DictReader(f))

    final_rows = []
    added = 0
    for i, prod in enumerate(products, 1):
        pt = prod["Product Type"]
        if pt in ui_map:
            row = ui_map[pt]
            row["No"] = str(i)
            final_rows.append(row)
        else:
            row = derive_ui_reasoning(prod)
            row["No"] = str(i)
            final_rows.append(row)
            added += 1

    with open(src, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(final_rows)

    print(f"\n  ✅ ui-reasoning.csv: {len(final_rows)} rows")
    print(f"     Added: {added} new reasoning rows")


# ─── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Rebuilding colors.csv ===")
    rebuild_colors()
    print("\n=== Rebuilding ui-reasoning.csv ===")
    rebuild_ui_reasoning()
    print("\n🎉 Done!")
