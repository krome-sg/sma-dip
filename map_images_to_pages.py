#!/usr/bin/env python3
"""
Utility script to map images to pages/posts from the Squarespace XML export.
This creates a JSON file showing which images are used on which pages.
"""

import xml.etree.ElementTree as ET
import json
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from collections import defaultdict

XML_FILE = "squarespace.xml"
IMG_URL = "images.squarespace-cdn.com"
OUTPUT_FILE = "image_to_page_mapping.json"

def extract_filename_from_url(url):
    """Extract the filename from a URL, handling query parameters."""
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    # If the filename contains query params (like ?format=original), remove them
    if '?' in filename:
        filename = filename.split('?')[0]
    return filename

def map_images_to_pages():
    """Extract mapping of images to pages from the XML file."""
    if not os.path.exists(XML_FILE):
        print(f"Error: {XML_FILE} not found in current directory")
        return
    
    namespace = {
        "content": "http://purl.org/rss/1.0/modules/content/",
        "wp": "http://wordpress.org/export/1.2/",
    }
    
    # Dictionary to store page -> images mapping
    page_to_images = defaultdict(set)
    # Dictionary to store image -> pages mapping (reverse)
    image_to_pages = defaultdict(set)
    
    tree = ET.parse(XML_FILE)
    root = tree.getroot()
    
    for item in root.findall("./channel/item"):
        # Skip attachment items (these are the images themselves)
        post_type = item.find("{%s}post_type" % namespace["wp"])
        if post_type is not None and post_type.text == "attachment":
            continue
        
        # Get page/post information
        title_element = item.find("title")
        title = title_element.text if title_element is not None else "unknown title"
        
        post_name_element = item.find("{%s}post_name" % namespace["wp"])
        post_name = post_name_element.text if post_name_element is not None else "unknown post name"
        
        # Create page identifier
        page_id = post_name
        page_info = {
            "title": title,
            "post_name": post_name,
            "markdown_file": f"{post_name}.md"
        }
        
        # Extract images from content:encoded
        content_element = item.find("{%s}encoded" % namespace["content"])
        if content_element is not None and content_element.text:
            content = content_element.text.replace("<![CDATA[", "").replace("]]>", "")
            soup = BeautifulSoup(content, "html.parser")
            for img in soup.find_all("img"):
                src = img.get("src")
                if src and IMG_URL in src:
                    # Normalize URL (add https if missing)
                    if not src.startswith(("http://", "https://")):
                        src = f"https://{src}"
                    filename = extract_filename_from_url(src)
                    page_to_images[page_id].add(src)
                    image_to_pages[src].add(page_id)
        
        # Extract images from link element
        for link_element in item.findall("link"):
            if link_element.text and IMG_URL in link_element.text:
                link_url = link_element.text
                if not link_url.startswith(("http://", "https://")):
                    link_url = f"https://{link_url}"
                filename = extract_filename_from_url(link_url)
                page_to_images[page_id].add(link_url)
                image_to_pages[link_url].add(page_id)
        
        # Extract images from wp:attachment_url
        for attachment_element in item.findall("{%s}attachment_url" % namespace["wp"]):
            if attachment_element.text and IMG_URL in attachment_element.text:
                attachment_url = attachment_element.text
                if not attachment_url.startswith(("http://", "https://")):
                    attachment_url = f"https://{attachment_url}"
                filename = extract_filename_from_url(attachment_url)
                page_to_images[page_id].add(attachment_url)
                image_to_pages[attachment_url].add(page_id)
    
    # Build output structure
    result = {
        "pages": {},
        "images": {},
        "summary": {
            "total_pages": len(page_to_images),
            "total_images": len(image_to_pages),
            "total_relationships": sum(len(images) for images in page_to_images.values())
        }
    }
    
    # Build pages dictionary
    for page_id, image_urls in page_to_images.items():
        result["pages"][page_id] = {
            "image_count": len(image_urls),
            "images": sorted(list(image_urls))
        }
    
    # Build images dictionary
    for image_url, page_ids in image_to_pages.items():
        filename = extract_filename_from_url(image_url)
        result["images"][image_url] = {
            "filename": filename,
            "used_on_pages": sorted(list(page_ids)),
            "page_count": len(page_ids)
        }
    
    # Write to JSON file
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Mapping completed!")
    print(f"  - Found {result['summary']['total_pages']} pages with images")
    print(f"  - Found {result['summary']['total_images']} unique images")
    print(f"  - Total image-page relationships: {result['summary']['total_relationships']}")
    print(f"  - Results saved to: {OUTPUT_FILE}")
    
    # Print some statistics
    print(f"\nTop 10 pages by image count:")
    sorted_pages = sorted(result["pages"].items(), key=lambda x: x[1]["image_count"], reverse=True)[:10]
    for page_id, data in sorted_pages:
        print(f"  - {page_id}: {data['image_count']} images")
    
    print(f"\nImages used on multiple pages:")
    multi_page_images = {url: info for url, info in result["images"].items() if info["page_count"] > 1}
    sorted_multi = sorted(multi_page_images.items(), key=lambda x: x[1]["page_count"], reverse=True)[:10]
    for url, info in sorted_multi:
        print(f"  - {info['filename']}: used on {info['page_count']} pages")
    
    return result

if __name__ == "__main__":
    map_images_to_pages()

