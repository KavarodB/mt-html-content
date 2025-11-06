"""
HTML Main Content Extractor V3
Improved to handle:
- Separated header and body sections
- Complete article extraction including all elements
- Better parent container detection
"""

import re
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
        """
        Find the header container including H1 and metadata (author, date, tags, etc.)
        Includes relevant siblings that might contain metadata
        """
        # Find all H1s and use the first one
        h1s = soup.find_all('h1')
        if not h1s:
            return None
            
        # Always use the first H1 as it's typically the main article headline
        h1 = h1s[0]
        
        # First look for semantic header container
        header_container = h1.find_parent('header')
        if header_container:
            return header_container
            
        # If no semantic header, look for div with header-like class/id
        for parent in h1.parents:
            if parent.name == 'body':
                break
                
            if parent.name in ['div', 'section']:
                classes = ' '.join(parent.get('class', [])).lower()
                id_attr = parent.get('id', '').lower()
                
                # Check if this looks like a header container
                if ('header' in classes or 'title' in classes or
                    'header' in id_attr or 'title' in id_attr or
                    'meta' in classes or 'info' in classes):
                    return parent
        
        # If no header container found, create one with H1 and nearby metadata
        result_soup = BeautifulSoup('<header class="extracted-header"></header>', 'html.parser')
        new_header = result_soup.header
        
        # Add the H1
        new_header.append(BeautifulSoup(str(h1), 'html.parser'))
        
        # Helper function to check if element might contain metadata
        def is_metadata_element(element: Tag) -> bool:
            if not isinstance(element, Tag):
                return False
                
            # Check element classes and content
            classes = ' '.join(element.get('class', [])).lower()
            text = element.get_text(strip=True).lower()
            
            metadata_patterns = [
                'author', 'byline', 'date', 'time', 'published',
                'meta', 'tag', 'category', 'topic', 'share', 'social'
            ]
            
            return any(pattern in classes or pattern in text for pattern in metadata_patterns)
        
        # Look for metadata in siblings
        current = h1
        # Look at previous siblings (usually where metadata is)
        for sibling in h1.find_previous_siblings():
            if is_metadata_element(sibling):
                new_header.insert(0, BeautifulSoup(str(sibling), 'html.parser'))
                
        # Look at next siblings (might contain subtitle, tags, etc)
        for sibling in h1.find_next_siblings():
            if is_metadata_element(sibling):
                new_header.append(BeautifulSoup(str(sibling), 'html.parser'))
            # Stop if we hit a paragraph or other content
            elif sibling.name in ['p', 'div'] and not is_metadata_element(sibling):
                break
        
        return new_header

    def extract(self, html: str) -> str:
        """
        Extract main content from HTML
        Strictly enforces H1 requirement - returns empty if H1 not found
        """
        # First quick check for H1
        if '<h1' not in html:
            print("  DEBUG [extract] No H1 found in HTML, skipping")
            return ""

        #Remove pure noise (footer,aside,nav,header,etc.) for easier parsing
        soup = BeautifulSoup(html, 'html.parser')
        self._remove_noise(soup)

        # Strategy 1: Find the header container with metadata
        print("  DEBUG [extract] Strategy 1: Finding header with metadata")
        header_container = self._find_h1_container(soup)
        if not header_container:
            print("  DEBUG [extract] No valid header container found")
            return ""

        # Strategy 2: Look for main content container
        print("  DEBUG [extract] Strategy 2: Finding main content container")
        body_container = self._find_article_container(soup)
        
        if not body_container:
            print("  DEBUG [extract] No valid content body found")
            return ""
        
        # Validate content body has enough paragraphs
        p_count = len(body_container.find_all('p'))
        if p_count < self.min_paragraph_count:
            print(f"  DEBUG [extract] Content body found with {p_count} paragraphs - Rejected")
            return ""
        
        print(f"  DEBUG [extract] Found main content container with {p_count} paragraphs")
        try:
            # Merge header and body content, removing duplicates
            print("  DEBUG [extract] Merging header and body content")
            merged_container = self._merge_content(header_container, body_container)
            
            result = str(merged_container)
            print(f"  DEBUG [before_clean] Merged content length: {len(result)} chars")
            return self._clean_extracted_content(result)
            
        except Exception as e:
            print(f"  DEBUG [extract] Error during merge: {str(e)}")
            # Fallback: return body content if merge fails
            return self._clean_extracted_content(str(body_container))
                
       
    
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
        """Find semantic article container using DFS to locate the most content-rich container"""
        print("  DEBUG [find_article] Starting semantic article search")
        
        def get_content_density(element: Tag) -> float:
            """Calculate content density including nested content"""
            # Consider all text content
            text_content = element.get_text(strip=True)
            paragraphs = len(element.find_all('p'))
            headings = len(element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']))
            
            # Calculate density metrics
            text_len = len(text_content)
            total_nodes = len(element.find_all(recursive=False))
            density = len(text_content) / max(total_nodes, 1)  # Avoid division by zero
            
            return density + (paragraphs * 100) + (headings * 50)
            
        def score_container(element: Tag, depth: int = 0) -> tuple[float, Tag]:
            """Score container and its children using DFS, returns (score, best_container)"""
            if not isinstance(element, Tag):
                return (0, None)
                
            # Base score from current element's content
            base_score = get_content_density(element)
            
            # Semantic markup bonus
            if element.name == 'article':
                base_score *= 1.5
            elif element.name == 'main':
                base_score *= 1.3
                
            # Find best child container
            best_child_score = 0
            best_child = None
            content_children = element.find_all(['div', 'article', 'main', 'section'], recursive=False)
            
            for child in content_children:
                child_score, child_container = score_container(child, depth + 1)
                if child_score > best_child_score:
                    best_child_score = child_score
                    best_child = child_container
            
            # Combine scores with depth penalty
            total_score = base_score + (best_child_score * 0.8)  # Child content weighted at 80%
            
            # If this element has more direct content than best child, return this element
            if base_score > best_child_score or not best_child:
                return (total_score, element)
            else:
                return (total_score, best_child)
        
        # Start DFS from potential containers
        candidates = []
        # First try root level containers
        for root in soup.find_all(['article', 'main'], recursive=False):
            score, container = score_container(root)
            if score > 0:
                candidates.append((score, container))
                
        # If no good candidates found, try all content containers
        if not candidates:
            for element in soup.find_all(['article', 'main', 'div[class*="content"]', 'div[class*="article"]']):
                score, container = score_container(element)
                if score > 0:
                    candidates.append((score, container))
        
        if not candidates:
            return None
            
        # Return the container with highest content score that meets minimum requirements
        candidates = [(score, container) for score, container in candidates 
                     if (len(container.find_all('p')) >= self.min_paragraph_count and
                         len(container.get_text(strip=True)) >= self.min_text_length)]
        
        if not candidates:
            return None
            
        best_score, best_container = max(candidates, key=lambda x: x[0])
        print(f"  DEBUG [find_article] Selected container with score {best_score:.2f} and {len(best_container.find_all('p'))} paragraphs")
        return best_container
    
    
    def _clone_element(self, element: Tag) -> Tag:
        """Clone a BeautifulSoup element"""
        return BeautifulSoup(str(element), 'html.parser').contents[0]
        
    def _merge_content(self, header: Tag, body: Tag) -> Tag:
        """
        Merge header and body content while removing duplicates and ensuring proper structure.
        Handles cases like duplicate subheaders, repeated metadata, etc.
        """
        result_soup = BeautifulSoup('<article class="extracted-content"></article>', 'html.parser')
        new_container = result_soup.article
        
        # Keep track of text content to avoid duplicates
        seen_text = set()
        seen_images = set()
        
        def is_duplicate(element: Tag) -> bool:
            """Check if an element is a duplicate based on its content"""
            if not isinstance(element, Tag):
                return False
                
            # For text elements, check content
            if element.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = element.get_text(strip=True)
                if text in seen_text:
                    print(f"  DEBUG [merge] Found duplicate text: {text[:100]}...")
                    return True
                seen_text.add(text)
                print(f"  DEBUG [merge] Added new {element.name}: {text[:100]}...")
                return False
                
            # For images, check src or data attributes
            if element.name in ['img', 'picture', 'figure']:
                img_src = element.get('src', '')
                if img_src in seen_images:
                    print(f"  DEBUG [merge] Found duplicate image: {img_src}")
                    return True
                seen_images.add(img_src)
                print(f"  DEBUG [merge] Added new image: {img_src}")
                # Also check nested images in figures
                if element.name == 'figure':
                    for img in element.find_all('img'):
                        img_src = img.get('src', '')
                        if img_src in seen_images:
                            print(f"  DEBUG [merge] Found duplicate nested image: {img_src}")
                            return True
                        seen_images.add(img_src)
                return False
                
            # For header elements, be more thorough
            if element.name == 'header':
                print(f"  DEBUG [merge] Processing header element with {len(element.contents)} children")
                # Process each child individually
                new_header = BeautifulSoup('<header class="article-header"></header>', 'html.parser').header
                has_content = False
                for child in element.children:
                    if isinstance(child, Tag) and not is_duplicate(child):
                        new_header.append(child)
                        has_content = True
                if has_content:
                    return new_header
                else:
                    print("  DEBUG [merge] Skipping empty or duplicate header")
                    return None
                
            return False
        
        print("  DEBUG [merge] Processing header content")
        # Process header first
        if header:
            header_content = BeautifulSoup(str(header), 'html.parser')
            print(f"  DEBUG [merge] Header has {len(header_content.contents)} elements")
            for element in header_content.children:
                if isinstance(element, Tag):
                    if element.name == 'header':
                        # Process header element specially
                        processed_header = is_duplicate(element)
                        if processed_header:
                            new_container.append(processed_header)
                    elif not is_duplicate(element):
                        new_container.append(element)
        
        print("  DEBUG [merge] Processing body content")
        # Process body content
        if body:
            body_content = BeautifulSoup(str(body), 'html.parser')
            print(f"  DEBUG [merge] Body has {len(body_content.contents)} elements")
            # Remove any H1s from body as they should be in header
            for h1 in body_content.find_all('h1'):
                print("  DEBUG [merge] Removing H1 from body")
                h1.decompose()
            
            # Add remaining body content, checking for duplicates
            for element in body_content.children:
                if isinstance(element, Tag):
                    if element.name == 'header':
                        # Process header element specially
                        processed_header = is_duplicate(element)
                        if processed_header:
                            new_container.append(processed_header)
                    elif not is_duplicate(element):
                        new_container.append(element)
        
        print(f"  DEBUG [merge] Merge complete. Final container has {len(new_container.contents)} elements")
        return new_container
    
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
                    
            # Check element's class and attributes for share/save
            if hasattr(element, 'attrs') and element.attrs:
                # Check class names
                if element.get('class'):
                    classes = ' '.join(element['class']).lower()
                    if 'share' in classes :
                        print(f"  DEBUG [clean] Removing element with share class")
                        return True
                    
                # Check all attributes (id, data-*, etc)
                attrs_str = ' '.join(str(v) for v in element.attrs.values() if v is not None).lower()
                if 'share' in attrs_str :
                    print(f"  DEBUG [clean] Removing element with share attribute")
                    return True
            
            # Check for related content in element string
            element_str = str(element).lower()
            if 'related' in element_str:
                # Only remove if it doesn't have paragraphs
                if not element.find_all('p'):
                    return True
                    
            # Check all attributes for share/save/related keywords
            if hasattr(element, 'attrs') and element.attrs:
                attrs_str = ' '.join(str(v) for v in element.attrs.values()).lower()
                # Check for share/save in attributes
                if 'share' in attrs_str or 'save' in attrs_str:
                    print(f"  DEBUG [clean] Removing element with share/save attributes")
                    return True
                    
                # Check for related in attributes
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