# test_vardplan_detection.py
#!/usr/bin/env python3
"""
Test script for vårdplan template analyzer
Run this to verify your template sections are being detected correctly
"""

from bs4 import BeautifulSoup

# Your template HTML (from the uploaded file)
TEMPLATE_HTML = """<span class="adminfont" id="admin_font" style="font-family: verdana; font-size: 8pt;"></span><table style="width: 700px;" cellspacing="0" cellpadding="0" width="99%"><tbody><tr><td><img alt="" src="Customer/stbe67/Logo/stbe67.gif" width="250">&nbsp;</td><td valign="top"><span style="font-family: verdana; font-size: 8pt;"><b>GENOMFÖRANDEPLAN </b><br><br><b>[Dagens datum]</b></span>&nbsp;</td><td valign="top"><span text="pageno"></span><br><br><span style="font-family: verdana; font-size: 8pt;"><b>[Förnamn] [Efternamn] </b><br><b>[Personnummer] </b></span>&nbsp;</td></tr></tbody></table><span class="adminfont" id="admin_font" style="font-family: verdana; font-size: 8pt;"><br></span><table style="width: 100%; border-collapse: collapse;" cellspacing="0" cellpadding="4"><tbody><tr><td style="border-width: 0px; width: 600px;" align="left" valign="top"><br><span style="font-size: 12pt;"><span style="font-family: verdana; font-size: 12pt;"><span style="font-weight: bold;">Socialsekreterare:</span></span><br><br><span style="font-family: verdana;"><span style="font-weight: bold;">Konsulent:</span></span><br><br><span style="font-family: verdana;"><span style="font-weight: bold;">Närvarande:</span></span><br><br><span style="font-family: verdana;"><span style="font-weight: bold;">AKTUELL SITUATION I FAMILJEHEMMET</span></span></span><span style="font-family: verdana; font-size: 8pt;"><br><br>Beskriv situationen i familjehem, när X placerades, hur de trivs med varandra etc.<br><br>Kan även skriva in andra rubriker nedan.....<br></span><span style="font-size: 12pt;"><span style="font-family: verdana; font-size: 12pt;"><span style="font-weight: bold;"><br>HÄLSA</span></span><br style="font-family: verdana;"><br style="font-family: verdana;"><span style="font-family: verdana;"><span style="font-weight: bold;">Mål</span></span></span><br><br>- Att x lär sig mer om diagnosen xx och vad det innebär för x.<br>- Att x skyddar sig mot sexuellt överfÃ¶rbara sjukdomar och oonskade graviditer.<br>- Att x tar ansvar för sin medicinering<br><br style="font-family: verdana;"><span style="font-family: verdana; font-size: 12pt;"><span style="font-weight: bold;">Insats och tidsram</span></span><br><br>- Att x med stöttning av familjehemmet håller de kontakter som behövs med sjukvården, BUP utifrån x:s medicinering.<br style="font-family: verdana;"><br style="font-family: verdana;"><span style="font-size: 12pt;"><span style="font-family: verdana; font-size: 12pt;"><span style="font-weight: bold;">UTBILDNING</span></span><br style="font-family: verdana;"><br style="font-family: verdana;"><span style="font-family: verdana;"><span style="font-weight: bold;">Mål</span></span></span><br><br>- Att x har.<br>- Att x utvecklas och blir bemött utifrån sin ålder och mognad.<br>- Att x <br>- Att x fortsätter ha positiva kompisrelationer.<br><br style="font-family: verdana;"><br style="font-family: verdana;"><span style="font-family: verdana; font-size: 12pt;"><span style="font-weight: bold;">Insats<br></span></span><br>- Att familjehemmet ger x stöd i att komma upp på morgonen och komma iväg till skolan.</td></tr></tbody></table>"""


def test_section_detection():
    """Test if sections are being detected correctly"""
    
    print("=" * 70)
    print("VÅRDPLAN TEMPLATE SECTION DETECTION TEST")
    print("=" * 70)
    print()
    
    soup = BeautifulSoup(TEMPLATE_HTML, 'html.parser')
    
    # Metadata keywords to skip
    metadata_keywords = [
        'vårdplan', 'genomförandeplan', 'namn', 'personnummer', 
        'socialsekreterare', 'konsulent', 'närvarande', 'dagens datum'
    ]
    
    sections_found = []
    
    print("🔍 Searching for sections...\n")
    
    # Find all bold elements (both tags and styles)
    for table in soup.find_all('table'):
        for cell in table.find_all(['td', 'th']):
            # Method 1: <strong> and <b> tags
            bold_tags = cell.find_all(['strong', 'b'])
            
            # Method 2: Spans with font-weight: bold
            styled_spans = cell.find_all('span', style=True)
            for span in styled_spans:
                style = span.get('style', '')
                if 'font-weight' in style and 'bold' in style:
                    bold_tags.append(span)
            
            for bold in bold_tags:
                text = bold.get_text(strip=True)
                
                # Skip if too short/long
                if not text or len(text) < 3 or len(text) > 100:
                    continue
                
                # Skip metadata
                is_meta = any(kw in text.lower() for kw in metadata_keywords)
                if is_meta:
                    print(f"  ⏭️  SKIP (metadata): {text}")
                    continue
                
                # Skip duplicates
                if text in sections_found:
                    print(f"  ⏭️  SKIP (duplicate): {text}")
                    continue
                
                # This is a section!
                sections_found.append(text)
                print(f"  ✅ FOUND: {text}")
    
    print()
    print("=" * 70)
    print(f"RESULTS: Found {len(sections_found)} sections")
    print("=" * 70)
    print()
    
    if len(sections_found) > 0:
        print("📋 Section List:")
        for i, section in enumerate(sections_found, 1):
            print(f"  {i}. {section}")
        print()
    
    # Expected sections
    expected = [
        'AKTUELL SITUATION I FAMILJEHEMMET',
        'HÄLSA',
        'Mål',
        'Insats och tidsram',
        'UTBILDNING',
        'KÄNSLOR OCH BETEENDE',
        'IDENTITET',
        'FAMILJ OCH SOCIALA RELATIONER',
        'SOCIALT UPPTRÄDANDE',
        'FÖRMÅGA ATT KLARA SIG SJÄLV',
        'UMGÄNGE'
    ]
    
    print("=" * 70)
    print("EXPECTED SECTIONS (should find at least these):")
    print("=" * 70)
    for exp in expected:
        found = exp in sections_found
        icon = "✅" if found else "❌"
        print(f"  {icon} {exp}")
    
    print()
    
    if len(sections_found) >= 5:
        print("🎉 SUCCESS! Template analyzer should work correctly.")
    else:
        print("⚠️  WARNING! Not enough sections detected.")
        print("   Expected at least 5, found:", len(sections_found))
    
    print()


if __name__ == "__main__":
    test_section_detection()