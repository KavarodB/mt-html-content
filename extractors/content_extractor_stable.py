"""
HTML Main Content Extractor V3
Improved to handle:
- Separated header and body sections
- Complete article extraction including all elements
- Better parent container detection
"""

import re
import hashlib
from typing import List, Tuple, Optional, Dict, Any, Set
from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag, NavigableString


@dataclass
class ContentCandidate:
    """Represents a potential content container"""
    element: Tag
    score: float
    text_length: int
    link_density: float
    has_article_structure: bool
    depth: int
    has_h1: bool
    p_count: int
    combined_with: Optional[Tag] = None  # For merged candidates


class ContentExtractorV3:
    """Enhanced content extraction that handles various article layouts"""
    
    def __init__(self):
        self.cache = {}
        
        # Content indicators
        self.content_tags = {'article', 'main', 'section', 'div'}
        self.heading_tags = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
        self.text_tags = {'p', 'span', 'li', 'td', 'blockquote'}
        self.media_tags = {'img', 'video', 'audio', 'picture', 'figure', 'iframe'}
        
        # Noise elements
        self.noise_tags = {
            'script', 'style', 'noscript', 'meta', 'link',
            'input', 'button', 'select', 'textarea', 'form',
            'footer', 'aside', 'nav'
        }
        
        # Patterns
        self.noise_patterns = re.compile(
            r'(nav|menu|sidebar|widget|social|share|comment|footer|header|'
            r'breadcrumb|pagination|advertisement|banner|popup|modal|overlay|'
            r'cookie|gdpr|consent|newsletter|signup|signin|login|register|'
            r'related|recommended|trending|popular|aside|tags|follow|subscribe|'
            r'also-read|more-stories|more-news|related-posts|related-articles|'
            r'you-may-like|suggested|promotion|sponsor|ad|ad-banner)',
            re.IGNORECASE
        )
        
        self.content_patterns = re.compile(
            r'(article|content|main|post|entry|story|text|body|'
            r'news|blog|detail|single|page-content|post-content)',
            re.IGNORECASE
        )
        
        self.header_patterns = re.compile(
            r'(header|headline|title|hero)',
            re.IGNORECASE
        )
        
        self.body_patterns = re.compile(
            r'(body|content|text|story|description)',
            re.IGNORECASE
        )
        
        # Thresholds - More aggressive values
        self.min_text_length = 150  # Increased minimum text length
        self.min_word_count = 35    # Increased minimum word count
        self.max_link_density = 0.3  # Reduced max link density
        self.min_paragraph_count = 3  # Increased minimum paragraph count
    
    def _find_h1_container(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find the smallest meaningful container that has the first H1 tag in the document"""
        
        # Find all H1s and use the first one (highest in the document)
        h1s = soup.find_all('h1')
        if not h1s:
            return None
            
        # Always use the first H1 as it's typically the main article headline
        h1 = h1s[0]
            
        # Walk up to find meaningful container
        container = h1.parent
        last_container = container
        
        # Walk up until we find the most relevant container
        while container and container.name != 'body':
            # Stop if we find an article or main tag
            if container.name in ['article', 'main']:
                return container
                
            # Stop at div if it has other meaningful content
            if container.name == 'div':
                # Check if this div has significant content
                has_content = (
                    bool(container.find('img')) or
                    bool(container.find(['h2', 'h3'])) or
                    len(container.find_all(['p', 'figure'])) > 0 or
                    len(container.get_text(strip=True)) > 500  # Significant text
                )
                if has_content:
                    return container
                    
            last_container = container
            container = container.parent
            container = container.parent
            
        # Don't go too high in the DOM
        if container and container.name in ['body', 'html']:
            # Fallback to closest div or original parent
            container = h1.find_parent(['div', 'header']) or h1.parent
            
        return container

    def extract(self, html: str) -> str:
        """
        Extract main content from HTML
        Strictly enforces H1 requirement - returns empty if H1 not found
        """
        # First quick check for H1
        if '<h1' not in html:
            print("  DEBUG [extract] No H1 found in HTML, skipping")
            return ""

        # Initial parse and summary
        initial_soup = BeautifulSoup(html, 'html.parser')
        h1s = initial_soup.find_all('h1')
        print(f"  DEBUG [extract] Found {len(h1s)} H1 tags in document")

        #Remove pure noise (footer,aside,nav,header,etc.) for easier parsing
        soup = BeautifulSoup(html, 'html.parser')
        self._remove_noise(soup)

        # Strategy 1: Look for semantic article container first
        print("  DEBUG [extract] Strategy 1: Looking for semantic article container")
        article_container = self._find_article_container(soup)
        if article_container:
            print(f"  DEBUG [extract] Found article container with tag <{article_container.name}>")
            if self._is_complete_article(article_container):
                # If article is complete, use it as is
                result = str(article_container)
                
                print(f"  DEBUG [before_clean] Complete article found, length: {len(result)} chars")
                return self._clean_extracted_content(result)
            
            else:
                # Article has content but H1 might be elsewhere - try to merge
                print("  DEBUG [extract] Article found but missing proper H1, attempting merge")
                
                # Find all H1s and get the first valid one
                h1s = soup.find_all('h1')
                first_h1 = None
                for h1 in h1s:
                    if isinstance(h1, Tag):  # Ensure it's a proper Tag
                        first_h1 = h1
                        break

                if first_h1:
                    print(f"  DEBUG [extract] Found H1: {first_h1.get_text(strip=True)}")
                    # Create new container with H1 and article content
                    result_soup = BeautifulSoup('<article class="extracted-content"></article>', 'html.parser')
                    new_container = result_soup.article
                    
                    try:
                        # Create new H1 element instead of copying
                        new_h1 = BeautifulSoup(str(first_h1), 'html.parser').h1
                        new_container.append(new_h1)
                        
                        # Add all content from article_container
                        article_content = BeautifulSoup(str(article_container), 'html.parser')
                        # Remove any existing H1s from article content
                        for h1 in article_content.find_all('h1'):
                            h1.decompose()
                        
                        # Add remaining content
                        for element in article_content.children:
                            if isinstance(element, Tag):
                                new_container.append(element)
                        
                        result = str(new_container)
                        print(f"  DEBUG [before_clean] Merged content length: {len(result)} chars")
                        return self._clean_extracted_content(result)
                    except Exception as e:
                        print(f"  DEBUG [extract] Error during merge: {str(e)}")
                        # Fallback: just return the article content
                        return self._clean_extracted_content(str(article_container))
                else:
                    print("  DEBUG [extract] No valid H1 found for merging")

        # Strategy 2: Find individual article candidates
        candidates = []
        
        # Start with <article> tags
        print("  DEBUG [extract] Strategy 2: Searching for article candidates")
        for article in soup.find_all('article'):
            if article.find('h1'):
                text_len = len(article.get_text(strip=True))
                if text_len >= self.min_text_length:
                    candidates.append(article)
        
        # If no complete articles found, try content divs with H1s
        if not candidates:
            for element in soup.find_all(['div', 'section']):
                h1 = element.find('h1')
                if h1:
                    text_len = len(element.get_text(strip=True))
                    if text_len >= self.min_text_length and len(element.find_all('p')) >= 2:
                        candidates.append(element)
        
        # Score and select best candidate
        if candidates:
            print(f"  DEBUG [extract] Found {len(candidates)} potential candidates to score")
            best_score = 0
            best_candidate = None
            
            for candidate in candidates:
                score = 0
                # Length score
                text_len = len(candidate.get_text(strip=True))
                score += min(text_len / 500, 20)
                
                # Structure score
                score += len(candidate.find_all('p')) * 2
                score += len(candidate.find_all('img')) * 3
                
                # Content indicators in class/id
                element_id = candidate.get('id', '')
                element_classes = ' '.join(candidate.get('class', []))
                if self.content_patterns.search(element_id):
                    score += 10
                if self.content_patterns.search(element_classes):
                    score += 10
                
                # Link density check
                links = candidate.find_all('a')
                if links:
                    link_text = sum(len(a.get_text(strip=True)) for a in links)
                    link_density = link_text / text_len
                    score *= (1 - link_density)
                
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            
            if best_candidate:
                print(f"  DEBUG [extract] Selected best candidate (score: {best_score:.2f})")
                result = str(best_candidate)
                # Verify single H1
                result_soup = BeautifulSoup(result, 'html.parser')
                if len(result_soup.find_all('h1')) == 1:
                    return self._clean_extracted_content(result)
        
        # Fallback: Try to find main content area with single H1
        main_elements = soup.find_all(['main', 'div', 'section'])
        for element in main_elements:
            h1s = element.find_all('h1')
            if len(h1s) == 1:
                text = element.get_text(strip=True)
                if len(text) >= self.min_text_length and len(element.find_all('p')) >= 2:
                    return self._clean_extracted_content(str(element))
        
        return ""
    
    def _is_complete_article(self, element: Tag) -> bool:
        """
        Check if an element contains a complete article
        Ensures the H1 is one of the first elements (not deep in the content)
        """
        h1s = element.find_all('h1')
        # Check if there's an H1 and it's one of the first few elements
        if h1s:
            first_h1 = h1s[0]
            # Count how many meaningful elements are before the H1
            elements_before = len([e for e in first_h1.find_previous_siblings(['p', 'div', 'section'])])
            if elements_before > 2:  # If H1 is too deep, this might be a comments section or similar
                return False
            has_h1 = True
        else:
            has_h1 = False

        p_count = len(element.find_all('p'))
        text_length = len(element.get_text(strip=True))
        print(f"  DEBUG [is_complete] Checking article: H1={has_h1}, paragraphs={p_count}, text_length={text_length}")
        
        # Complete article should have headline and substantial content
        return has_h1 and p_count >= self.min_paragraph_count and text_length >= self.min_text_length * 2
    
    def _remove_noise(self, soup: BeautifulSoup):
        """Remove footer, header, audio blocks, and external links while preserving essential content"""
        # First, protect H1 containers
        h1_elements = soup.find_all('h1')
        protected_elements = set()
        
        for h1 in h1_elements:
            protected_elements.add(h1)  # Protect H1 itself
            # Protect H1's direct parent
            if h1.parent:
                protected_elements.add(h1.parent)
        
        # Remove headers, footers, and asides
        elements_to_remove = []
        
        for element in soup.find_all(['header', 'footer', 'aside','nav']):
            # Skip if it contains or is a protected element
            if element in protected_elements or element.find(lambda tag: tag in protected_elements):
                continue
            elements_to_remove.append(element)
        
        # Remove audio-related elements
        audio_pattern = re.compile(r'audio|player|podcast|sound', re.IGNORECASE)
        
        for element in soup.find_all(['audio', 'time','svg']):  # Audio tags and time tags (often used for audio players)
            elements_to_remove.append(element)
            
        for element in soup.find_all(True):  # Check all elements for audio-related classes/IDs
            if element in protected_elements:
                continue
                
            # Check element attributes for audio-related terms
            if hasattr(element, 'attrs'):
                attrs_str = ' '.join(str(v) for v in element.attrs.values()).lower()
                if audio_pattern.search(attrs_str):
                    elements_to_remove.append(element)

        # Remove external links and their parents
        link_count = 0
        for link in soup.find_all('a'):
            if link in protected_elements:
                continue
                
            # Check for href and target attributes
            href = link.get('href')
            target = link.get('target', '').lower()
            
            if href or (target in ['_self', '_blank']):
                # If the link is in a paragraph, preserve the text
                if link.find_parent('p'):
                    text = link.get_text(strip=True)
                    if text:
                        link.replace_with(text)
                    else:
                        link.decompose()
                else:
                    # Remove link's parent if it's not a protected element or main container
                    parent = link.parent
                    if (parent and 
                        parent not in protected_elements and 
                        parent.name not in ['article', 'main', 'div', 'section', 'body', 'html']):
                        elements_to_remove.append(parent)
                    else:
                        link.decompose()
                link_count += 1
        
        # Remove the identified elements
        for element in elements_to_remove:
            if element.parent:
                element.decompose()
        
        print(f"  DEBUG [remove_noise] Removed {len(elements_to_remove)} noise elements and {link_count} external links")
    
    def _find_article_container(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find semantic article container"""
        print("  DEBUG [find_article] Starting semantic article search")
        best_article = None
        best_article_score = 0

        def score_article(element: Tag) -> float:
            """Score an article element based on content quality"""
            score = 0
            text = element.get_text(strip=True)
            text_len = len(text)
            
            # Base text length score
            score += min(text_len / 500, 20)  # Up to 20 points for length
            
            # Content structure
            if element.find('h1'):
                score += 25  # Strong bonus for having H1
            score += len(element.find_all('p')) * 2  # Points for paragraphs
            score += len(element.find_all('img')) * 3  # Points for images
            
            # Link density penalty
            links = element.find_all('a')
            if links:
                link_text = sum(len(a.get_text(strip=True)) for a in links)
                link_density = link_text / max(text_len, 1)
                score *= (1 - link_density)  # Reduce score based on link density
            
            # Check for article markup
            if element.name == 'article':
                score *= 1.5  # 50% bonus for proper article markup
            
            return score
        
        # Priority 1: <article> tags
        articles = soup.find_all('article')
        for article in articles:
            text = article.get_text(strip=True)
            if len(text) >= self.min_text_length:
                score = score_article(article)
                if score > best_article_score:
                    best_article_score = score
                    best_article = article
        
        # Priority 2: <main> tag but only if no good article found
        if not best_article or best_article_score < 30:
            mains = soup.find_all('main')
            for main in mains:
                text = main.get_text(strip=True)
                if len(text) >= self.min_text_length:
                    score = score_article(main)
                    if score > best_article_score:
                        best_article_score = score
                        best_article = main
        
        # Priority 3: role attributes
        if not best_article or best_article_score < 30:
            for role in ['main', 'article']:
                elements = soup.find_all(attrs={'role': role})
                for element in elements:
                    text = element.get_text(strip=True)
                    if len(text) >= self.min_text_length:
                        score = score_article(element)
                        if score > best_article_score:
                            best_article_score = score
                            best_article = element
        
        # Priority 4: Content patterns in id/class
        if not best_article or best_article_score < 30:
            for element in soup.find_all(['div', 'section']):
                element_id = element.get('id', '')
                element_classes = ' '.join(element.get('class', []))
                
                if (self.content_patterns.search(element_id) or 
                    self.content_patterns.search(element_classes)):
                    
                    text = element.get_text(strip=True)
                    if len(text) >= self.min_text_length:
                        # Additional validation
                        has_content = (
                            bool(element.find(self.heading_tags)) or
                            len(element.find_all('p')) >= 1
                        )
                        
                        if has_content:
                            score = score_article(element)
                            if score > best_article_score:
                                best_article_score = score
                                best_article = element
        
        return best_article
    
    
    def _clone_element(self, element: Tag) -> Tag:
        """Clone a BeautifulSoup element"""
        return BeautifulSoup(str(element), 'html.parser').contents[0]
    
    def _clean_extracted_content(self, html_content: str) -> str:
        """
        Final cleanup of extracted content:
        1. Removes redundant single-child containers
        2. Removes containers with short linked text
        3. Removes related content containers
        4. Removes interactive elements and their containers
        5. Recursively removes empty containers
        """
        # First analyze the content
        #self._analyze_content_before_clean(html_content)
        
        print("  DEBUG [clean] Starting final content cleanup")
        if not html_content or '<h1' not in html_content:
            print("  DEBUG [clean] No content or missing H1, rejecting")
            return ""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Interactive elements to remove
        interactive_tags = {
            'button', 'input', 'select', 'textarea', 'form',
            'dialog', 'details', 'menu', 'menuitem', 
            'iframe', 'embed', 'object','audio','time'
        }
        
        def is_empty_container(element: Tag) -> bool:
            """Check if element is empty or only contains whitespace"""
            try:
                # Skip if element is None or not a Tag
                if element is None or not isinstance(element, Tag):
                    return False
                    
                # Skip actual content elements
                if getattr(element, 'name', '') in ['img', 'video','figure','picture']:
                    return False
                    
                # Check text content
                text = element.get_text(strip=True) if hasattr(element, 'get_text') else ''
                return not bool(text)
            except Exception as e:
                print(f"  DEBUG [clean] Error in is_empty_container: {str(e)}")
                return False
            
        def should_remove_container(element: Tag) -> bool:
            """Determine if a container should be removed based on our criteria"""
            # Skip if element is None or a NavigableString
            if element is None or not isinstance(element, Tag):
                return False

            # Skip if it's the main container or contains H1
            if element.find('h1') or element.name in ['html', 'body']:
                return False
                
            # Never remove paragraphs or article containers
            if element.name in ['p', 'article']:
                return False
                
            # Skip if element contains multiple paragraphs
            if len(element.find_all('p', recursive=False)) > 1:
                return False
                
            # Check for interactive elements and their containers
            if (getattr(element, 'name', '') in interactive_tags or 
                any(child.name in interactive_tags for child in element.find_all())):
                # Only return True if this isn't a main content container
                if not element.find_all(['p', 'img', 'h1', 'h2', 'h3']):
                    return True
                
            # Only remove standalone links/spans with very short text
            if getattr(element, 'name', '') in ['a', 'span']:
                # Don't remove if it's inside a paragraph
                if element.find_parent('p'):
                    return False
                # Only remove if very short (less than 5 words)
                text = element.get_text(strip=True) if hasattr(element, 'get_text') else ''
                word_count = len(text.split())
                if word_count < 10:
                    return True
                    
            # Check for related content
            element_str = str(element).lower()
            if 'related' in element_str:
                # Only remove if it doesn't have paragraphs
                if not element.find_all('p'):
                    return True
                    
            # Check all attributes for 'related' keyword
            if hasattr(element, 'attrs') and element.attrs:
                for attr in element.attrs.values():
                    if isinstance(attr, str) and 'related' in attr.lower():
                        # Only remove if it doesn't have paragraphs
                        if not element.find_all('p'):
                            return True
                    elif isinstance(attr, list) and any('related' in str(v).lower() for v in attr):
                        # Only remove if it doesn't have paragraphs
                        if not element.find_all('p'):
                            return True
                            
            return False
            
        def clean_pass() -> int:
            """Perform one cleaning pass, return number of elements removed"""
            removed = 0
            
            try:
                # Remove sections and divs without p tags or h1
                for element in soup.find_all(['div', 'section']):
                    if not isinstance(element, Tag) or not element.parent:
                        continue
                    if element.name in ['html', 'body']:
                        continue
                        
                    # Check if element contains any important content
                    has_p = bool(element.find_all('p'))
                    has_h1 = bool(element.find_all('h1'))
                    has_media = bool(element.find_all(['img', 'picture', 'figure', 'video']))
                    
                    # Remove if no important content
                    if not (has_p or has_h1 or has_media):
                        # Before removing, make sure we preserve any nested important content
                        nested_content = []
                        for child in element.find_all(['p', 'h1', 'img', 'picture', 'figure', 'video']):
                            nested_content.append(child.extract())
                        
                        # Insert preserved content before removing the container
                        for content in nested_content:
                            element.insert_before(content)
                            
                        element.decompose()
                        removed += 1
                        continue
                        
                    # Don't remove if it contains paragraphs directly
                    if len(element.find_all('p', recursive=False)) > 0:
                        continue
                        
                    try:
                        children = list(element.find_all(recursive=False))
                        if len(children) == 1 and getattr(children[0], 'name', '') in ['article', 'main', 'div', 'section']:
                            # Before replacing, ensure we're not losing any attributes that might be needed
                            child = children[0]
                            # Preserve important attributes if child doesn't have them
                            for attr in ['id', 'class']:
                                if attr in element.attrs and attr not in child.attrs:
                                    child[attr] = element[attr]
                            element.replace_with(child)
                            removed += 1
                    except Exception as e:
                        print(f"  DEBUG [clean] Error processing single-child container: {str(e)}")
                
                # 2 & 3 & 4. Remove containers based on our criteria
                for element in soup.find_all():
                    if not isinstance(element, Tag):
                        continue
                        
                    if should_remove_container(element):
                        try:
                            # If it's an interactive element, also remove its parent container
                            if (getattr(element, 'name', '') in interactive_tags and 
                                element.parent and 
                                isinstance(element.parent, Tag)):
                                # Only remove parent if it doesn't have other content
                                parent = element.parent
                                if (getattr(parent, 'name', '') not in ['html', 'body'] and
                                    not parent.find_all('p') and
                                    len(parent.get_text(strip=True).split()) < 10):
                                    parent.decompose()
                                    removed += 1
                                else:
                                    # Just remove the interactive element
                                    element.decompose()
                                    removed += 1
                            else:
                                # Preserve paragraphs when removing containers
                                if element.find_all('p'):
                                    # Extract paragraphs before removing the container
                                    paragraphs = element.find_all('p')
                                    for p in paragraphs:
                                        element.insert_before(p)
                                element.decompose()
                                removed += 1
                        except Exception as e:
                            print(f"  DEBUG [clean] Error removing container: {str(e)}")
                
                # 5. Remove empty containers
                for element in soup.find_all():
                    if not isinstance(element, Tag):
                        continue
                    if getattr(element, 'name', '') not in ['img', 'video','figure','picture']:
                        try:
                            if is_empty_container(element):
                                # Don't remove if it's a direct parent of important content
                                if not element.find_all(['p', 'img', 'h1', 'h2', 'h3','picture'], recursive=False):
                                    element.decompose()
                                    removed += 1
                        except Exception as e:
                            print(f"  DEBUG [clean] Error removing empty container: {str(e)}")
                
                return removed
            except Exception as e:
                print(f"  DEBUG [clean] Error in clean_pass: {str(e)}")
                return 0
        
        # Perform cleaning passes until no more elements are removed
        total_removed = 0
        while True:
            removed = clean_pass()
            if removed == 0:
                break
            total_removed += removed
            
        # Standardize media dimensions before returning
        self._standardize_media_dimensions(soup)
        
        result = str(soup)
        print(f"  DEBUG [clean] Final cleanup complete - Removed {total_removed} elements, Content length: {len(result)} chars")
        
        return result
        
    def _standardize_media_dimensions(self, soup: BeautifulSoup) -> None:
        """Set standard dimensions for all media elements"""
        # List of media elements to process
        media_selectors = ['img', 'video', 'picture', 'iframe[src*="video"]']
        
        for selector in media_selectors:
            for element in soup.select(selector):
                if element.name == 'source':
                    # Handle source elements within picture tags
                    element['width'] = '256'
                    element['height'] = '256'
                else:
                    # Handle direct media elements
                    element['style'] = 'width: 256px; height: 256px; object-fit: cover;'
                    element['width'] = '256'
                    element['height'] = '256'
                    
                    # Remove any existing size-related attributes that might conflict
                    for attr in ['data-width', 'data-height', 'sizes']:
                        if attr in element.attrs:
                            del element[attr]
                
        # Also process picture elements themselves
        for picture in soup.find_all('picture'):
            picture['style'] = 'width: 256px; height: 256px; display: inline-block;'


def extract_main_content(html: str) -> str:
    extractor = ContentExtractorV3()
    return extractor.extract(html)


if __name__ == "__main__":
    print("Content Extractor V3 - Ready for testing")