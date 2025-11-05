import os
from bs4 import BeautifulSoup
from extractors.content_extractor import extract_main_content

# Global input and output directories
input_dir_name = "scraped"
output_dir_name = "content"


def test_content_extractor():
    """
    Test ContentExtractor on all HTML files in the scrapped folder.
    Saves extracted content to a parallel directory structure.
    """
    # Create output directory
    os.makedirs(output_dir_name, exist_ok=True)

    # Get all HTML files from scrapped directory
    scrapped_files = ["forbes.com_338d9cff6a.html","aljazeera.com_57cd2fa7e2.html","dw.com_54324f895c.html","dw.com_be117b6e0b.html","heraldscotland.com_b0edcabe65.html",
                      "vesti.bg_fd30260576.html"
    ]
    
    print(f"\nTesting ContentExtractor on {len(scrapped_files)} files")
    print("=" * 65 + "\n")

    for idx, filename in enumerate(scrapped_files, 1):
        input_path = os.path.join(input_dir_name, filename)
        output_path = os.path.join(output_dir_name, filename)
        
        print(f"[{idx}/{len(scrapped_files)}] Processing: {filename}")
        
        try:
            # Read input HTML
            with open(input_path, 'r', encoding='utf-8') as f:
                html = f.read()
                
            # Get original URL from comment if available
            url = ""
            if "<!-- Original URL:" in html:
                url = html.split("<!-- Original URL:")[1].split("-->")[0].strip()
            
            print(f"  Source: {url or input_path}")
            print(f"  Original size: {len(html)} chars")
            
            # Extract content
            extracted_html = extract_main_content(html)
            
            if not extracted_html:
                print("  WARNING: No content extracted")
                continue
                
            # Calculate reduction percentage
            reduction_pct = ((len(html) - len(extracted_html)) / len(html)) * 100
            print(f"  Extracted size: {len(extracted_html)} chars")
            print(f"  Reduction: {reduction_pct:.1f}%")
            
            # Get text stats
            soup = BeautifulSoup(extracted_html, 'html.parser')
            has_h1 = bool(soup.find('h1'))
            paragraphs = len(soup.find_all('p'))
            print(f"  Content check - Has H1: {has_h1}, Paragraphs: {paragraphs}")
            
            # Save extracted content
            with open(output_path, 'w', encoding='utf-8') as f:
                if url:
                    f.write(f"<!-- Original URL: {url} -->\n")
                f.write(f"<!-- Source file: {filename} -->\n")
                f.write(f"<!-- Original size: {len(html)} chars -->\n")
                f.write(f"<!-- Extracted size: {len(extracted_html)} chars -->\n")
                f.write(f"<!-- Reduction: {reduction_pct:.1f}% -->\n")
                f.write(f"<!-- Has H1: {has_h1}, Paragraphs: {paragraphs} -->\n\n")
                f.write(extracted_html)
            
            print(f"  Saved: {output_path}\n")
            
        except Exception as e:
            print(f"  ERROR: {str(e)}\n")
            continue

    print("=" * 65)
    print("DONE! Results saved in extracted_content/")
    print("=" * 65)

if __name__ == "__main__":
    test_content_extractor()